# -*- coding: utf-8 -*-
from odoo import models, fields, api
from collections import defaultdict
from collections import OrderedDict
import json
import re
import uuid
from functools import partial

from lxml import etree
from dateutil.relativedelta import relativedelta
from werkzeug.urls import url_encode

from odoo import api, exceptions, fields, models, _
from odoo.tools import email_re, email_split, email_escape_char, float_is_zero, float_compare, \
    pycompat, date_utils
from odoo.tools.misc import formatLang

from odoo.exceptions import AccessError, UserError, RedirectWarning, ValidationError, Warning

from odoo.addons import decimal_precision as dp
import logging

class AccountMove(models.Model):
    _inherit = "account.move"

    def _prepare_edi_tax_details(self, filter_to_apply=None, filter_invl_to_apply=None, grouping_key_generator=None, compute_mode='tax_details'):
        ''' Compute amounts related to taxes for the current invoice.

        :param filter_to_apply:         Optional filter to exclude some tax values from the final results.
                                        The filter is defined as a method getting a dictionary as parameter
                                        representing the tax values for a single repartition line.
                                        This dictionary contains:

            'base_line_id':             An account.move.line record.
            'tax_id':                   An account.tax record.
            'tax_repartition_line_id':  An account.tax.repartition.line record.
            'base_amount':              The tax base amount expressed in company currency.
            'tax_amount':               The tax amount expressed in company currency.
            'base_amount_currency':     The tax base amount expressed in foreign currency.
            'tax_amount_currency':      The tax amount expressed in foreign currency.

                                        If the filter is returning False, it means the current tax values will be
                                        ignored when computing the final results.

        :param filter_invl_to_apply:    Optional filter to exclude some invoice lines.

        :param grouping_key_generator:  Optional method used to group tax values together. By default, the tax values
                                        are grouped by tax. This parameter is a method getting a dictionary as parameter
                                        (same signature as 'filter_to_apply').

                                        This method must returns a dictionary where values will be used to create the
                                        grouping_key to aggregate tax values together. The returned dictionary is added
                                        to each tax details in order to retrieve the full grouping_key later.

        :param compute_mode:            Optional parameter to specify the method used to allocate the tax line amounts
                                        among the invoice lines:
                                        'tax_details' (the default) uses the AccountMove._get_query_tax_details method.
                                        'compute_all' uses the AccountTax._compute_all method.

                                        The 'tax_details' method takes the tax line balance and allocates it among the
                                        invoice lines to which that tax applies, proportionately to the invoice lines'
                                        base amounts. This always ensures that the sum of the tax amounts equals the
                                        tax line's balance, which, depending on the constraints of a particular
                                        localization, can be more appropriate when 'Round Globally' is set.

                                        The 'compute_all' method returns, for each invoice line, the exact tax amounts
                                        corresponding to the taxes applied to the invoice line. Depending on the
                                        constraints of the particular localization, this can be more appropriate when
                                        'Round per Line' is set.

        :return:                        The full tax details for the current invoice and for each invoice line
                                        separately. The returned dictionary is the following:

            'base_amount':              The total tax base amount in company currency for the whole invoice.
            'tax_amount':               The total tax amount in company currency for the whole invoice.
            'base_amount_currency':     The total tax base amount in foreign currency for the whole invoice.
            'tax_amount_currency':      The total tax amount in foreign currency for the whole invoice.
            'tax_details':              A mapping of each grouping key (see 'grouping_key_generator') to a dictionary
                                        containing:

                'base_amount':              The tax base amount in company currency for the current group.
                'tax_amount':               The tax amount in company currency for the current group.
                'base_amount_currency':     The tax base amount in foreign currency for the current group.
                'tax_amount_currency':      The tax amount in foreign currency for the current group.
                'group_tax_details':        The list of all tax values aggregated into this group.

            'invoice_line_tax_details': A mapping of each invoice line to a dictionary containing:

                'base_amount':          The total tax base amount in company currency for the whole invoice line.
                'tax_amount':           The total tax amount in company currency for the whole invoice line.
                'base_amount_currency': The total tax base amount in foreign currency for the whole invoice line.
                'tax_amount_currency':  The total tax amount in foreign currency for the whole invoice line.
                'tax_details':          A mapping of each grouping key (see 'grouping_key_generator') to a dictionary
                                        containing:

                    'base_amount':          The tax base amount in company currency for the current group.
                    'tax_amount':           The tax amount in company currency for the current group.
                    'base_amount_currency': The tax base amount in foreign currency for the current group.
                    'tax_amount_currency':  The tax amount in foreign currency for the current group.
                    'group_tax_details':    The list of all tax values aggregated into this group.

        '''
        self.ensure_one()

        def _serialize_python_dictionary(vals):
            return '-'.join(str(vals[k]) for k in sorted(vals.keys()))

        def default_grouping_key_generator(tax_values):
            return {'tax': tax_values['tax_id']}

        def compute_invoice_lines_tax_values_dict_from_tax_details(invoice_lines):
            invoice_lines_tax_values_dict = defaultdict(list)
            tax_details_query, tax_details_params = invoice_lines._get_query_tax_details_from_domain([('move_id', '=', self.id)])
            self._cr.execute(tax_details_query, tax_details_params)
            for row in self._cr.dictfetchall():
                invoice_line = invoice_lines.browse(row['base_line_id'])
                tax_line = invoice_lines.browse(row['tax_line_id'])
                src_line = invoice_lines.browse(row['src_line_id'])
                tax = self.env['account.tax'].browse(row['tax_id'])
                print("259++++++",tax)
                src_tax = self.env['account.tax'].browse(row['group_tax_id']) if row['group_tax_id'] else tax
                print("261 +++++++++++",src_tax)

                invoice_lines_tax_values_dict[invoice_line].append({
                    'base_line_id': invoice_line,
                    'tax_line_id': tax_line,
                    'src_line_id': src_line,
                    'tax_id': tax,
                    'src_tax_id': src_tax,
                    'tax_repartition_line_id': tax_line.tax_repartition_line_id,
                    'base_amount': row['base_amount'],
                    'tax_amount': row['tax_amount'],
                    'base_amount_currency': row['base_amount_currency'],
                    'tax_amount_currency': row['tax_amount_currency'],
                })
            return invoice_lines_tax_values_dict

        def compute_invoice_lines_tax_values_dict_from_compute_all(invoice_lines):
            invoice_lines_tax_values_dict = {}
            sign = -1 if self.is_inbound() else 1
            for invoice_line in invoice_lines:
                tax_id_ieps = []
                for t in invoice_line.tax_ids:
                    if t.ieps == False:
                        tax_id_ieps.append(t.id)
                    print("++++invoice_line+++++++",t.ieps)
                tax = self.env['account.tax'].browse(tax_id_ieps)
                print("++++taxes_res+++++++",invoice_line.tax_ids,tax)
                taxes_res = tax.compute_all(
                    invoice_line.price_unit * (1 - (invoice_line.discount / 100.0)),
                    currency=invoice_line.currency_id,
                    quantity=invoice_line.quantity,
                    product=invoice_line.product_id,
                    partner=invoice_line.partner_id,
                    is_refund=invoice_line.move_id.move_type in ('in_refund', 'out_refund'),
                )
                #raise UserError(_("xxxxx"))
                invoice_lines_tax_values_dict[invoice_line] = []
                rate = abs(invoice_line.balance) / abs(invoice_line.amount_currency) if invoice_line.amount_currency else 0.0
                for tax_res in taxes_res['taxes']:
                    invoice_lines_tax_values_dict[invoice_line].append({
                        'base_line_id': invoice_line,
                        'tax_id': self.env['account.tax'].browse(tax_res['id']),
                        'tax_repartition_line_id': self.env['account.tax.repartition.line'].browse(tax_res['tax_repartition_line_id']),
                        'base_amount': sign * invoice_line.company_currency_id.round(tax_res['base'] * rate),
                        'tax_amount': sign * invoice_line.company_currency_id.round(tax_res['amount'] * rate),
                        'base_amount_currency': sign * tax_res['base'],
                        'tax_amount_currency': sign * tax_res['amount'],
                    })
            print("307 invoice_lines_tax_values_dict",invoice_lines_tax_values_dict)
            return invoice_lines_tax_values_dict

        # Compute the taxes values for each invoice line.
        invoice_lines = self.invoice_line_ids.filtered(lambda line: not line.display_type)
        if filter_invl_to_apply:
            invoice_lines = invoice_lines.filtered(filter_invl_to_apply)

        if compute_mode == 'compute_all':
            invoice_lines_tax_values_dict = compute_invoice_lines_tax_values_dict_from_compute_all(invoice_lines)
        else:
            invoice_lines_tax_values_dict = compute_invoice_lines_tax_values_dict_from_tax_details(invoice_lines)

        grouping_key_generator = grouping_key_generator or default_grouping_key_generator

        # Apply 'filter_to_apply'.

        if self.move_type in ('out_refund', 'in_refund'):
            tax_rep_lines_field = 'refund_repartition_line_ids'
        else:
            tax_rep_lines_field = 'invoice_repartition_line_ids'

        filtered_invoice_lines_tax_values_dict = {}
        for invoice_line in invoice_lines:
            print("331 for invoice_line in invoice_lines")
            tax_values_list = invoice_lines_tax_values_dict.get(invoice_line, [])
            print("333 tax_values_list",tax_values_list)
            filtered_invoice_lines_tax_values_dict[invoice_line] = []

            # Search for unhandled taxes.
            taxes_set = set(invoice_line.tax_ids.flatten_taxes_hierarchy())
            print("337  taxes_set",taxes_set)
            for tax_values in tax_values_list:
                taxes_set.discard(tax_values['tax_id'])

                if not filter_to_apply or filter_to_apply(tax_values):
                    filtered_invoice_lines_tax_values_dict[invoice_line].append(tax_values)

            #print("tax_values['tax_line_id']",tax_values['tax_line_id'])
            #raise UserError(_("xxxxx"))
            # Restore zero-tax tax details.
            print("346 taxes_set",taxes_set)

            for zero_tax in taxes_set:

                if zero_tax.ieps == False:

                    affect_base_amount = 0.0
                    affect_base_amount_currency = 0.0
                    print("tax_values_list",tax_values_list)
                    raise UserError(_("xxxxx"))
                    for tax_values in tax_values_list:
                        if zero_tax in tax_values['tax_line_id'].tax_ids:
                            affect_base_amount += tax_values['tax_amount']
                            affect_base_amount_currency += tax_values['tax_amount_currency']

                    for tax_rep in zero_tax[tax_rep_lines_field].filtered(lambda x: x.repartition_type == 'tax'):
                        tax_values = {
                            'base_line_id': invoice_line,
                            'tax_line_id': self.env['account.move.line'],
                            'src_line_id': invoice_line,
                            'tax_id': zero_tax,
                            'src_tax_id': zero_tax,
                            'tax_repartition_line_id': tax_rep,
                            'base_amount': invoice_line.balance + affect_base_amount,
                            'tax_amount': 0.0,
                            'base_amount_currency': invoice_line.amount_currency + affect_base_amount_currency,
                            'tax_amount_currency': 0.0,
                        }

                        if not filter_to_apply or filter_to_apply(tax_values):
                            filtered_invoice_lines_tax_values_dict[invoice_line].append(tax_values)

        # Initialize the results dict.

        invoice_global_tax_details = {
            'base_amount': 0.0,
            'tax_amount': 0.0,
            'base_amount_currency': 0.0,
            'tax_amount_currency': 0.0,
            'tax_details': defaultdict(lambda: {
                'base_amount': 0.0,
                'tax_amount': 0.0,
                'base_amount_currency': 0.0,
                'tax_amount_currency': 0.0,
                'group_tax_details': [],
            }),
            'invoice_line_tax_details': defaultdict(lambda: {
                'base_amount': 0.0,
                'tax_amount': 0.0,
                'base_amount_currency': 0.0,
                'tax_amount_currency': 0.0,
                'tax_details': defaultdict(lambda: {
                    'base_amount': 0.0,
                    'tax_amount': 0.0,
                    'base_amount_currency': 0.0,
                    'tax_amount_currency': 0.0,
                    'group_tax_details': [],
                }),
            }),
        }

        # Apply 'grouping_key_generator' to 'invoice_lines_tax_values_list' and add all values to the final results.

        for invoice_line in invoice_lines:
            tax_values_list = filtered_invoice_lines_tax_values_dict[invoice_line]

            key_by_tax = {}

            # Add to invoice global tax amounts.
            invoice_global_tax_details['base_amount'] += invoice_line.balance
            invoice_global_tax_details['base_amount_currency'] += invoice_line.amount_currency

            for tax_values in tax_values_list:
                grouping_key = grouping_key_generator(tax_values)
                serialized_grouping_key = _serialize_python_dictionary(grouping_key)
                key_by_tax[tax_values['tax_id']] = serialized_grouping_key

                # Add to invoice line global tax amounts.
                if serialized_grouping_key not in invoice_global_tax_details['invoice_line_tax_details'][invoice_line]:
                    invoice_line_global_tax_details = invoice_global_tax_details['invoice_line_tax_details'][invoice_line]
                    invoice_line_global_tax_details.update({
                        'base_amount': invoice_line.balance,
                        'base_amount_currency': invoice_line.amount_currency,
                    })
                else:
                    invoice_line_global_tax_details = invoice_global_tax_details['invoice_line_tax_details'][invoice_line]

                self._add_edi_tax_values(invoice_global_tax_details, grouping_key, serialized_grouping_key, tax_values,
                                         key_by_tax=key_by_tax if compute_mode == 'tax_details' else None)
                self._add_edi_tax_values(invoice_line_global_tax_details, grouping_key, serialized_grouping_key, tax_values,
                                         key_by_tax=key_by_tax if compute_mode == 'tax_details' else None)

        return invoice_global_tax_details
