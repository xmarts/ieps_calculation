# -*- coding: utf-8 -*-
from odoo import models, fields, api
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

    @api.onchange('invoice_line_ids')
    def _onchange_invoice_line_ids(self):
        current_invoice_lines = self.line_ids.filtered(lambda line: not line.exclude_from_invoice_tab)
        others_lines = self.line_ids - current_invoice_lines
        if others_lines and current_invoice_lines - self.invoice_line_ids:
            others_lines[0].recompute_tax_line = True
        self.line_ids = others_lines + self.invoice_line_ids
        self._onchange_recompute_dynamic_lines()

    def _get_values_ieps(self):
        for rec in self:
            for l in rec.edi_document_ids:
                cfdi_3_3_edi = self.env.ref('l10n_mx_edi.edi_cfdi_3_3')
                if l.edi_format_id == cfdi_3_3_edi:
                    invoice = l.move_id
                    xml = l.edi_format_id._l10n_mx_edi_get_invoice_cfdi_values(invoice)
                    print("+++++",xml['tax_details_transferred'])
                    for l in xml['tax_details_transferred']:
                        print("lll",l)
                    raise UserError(_("xxx"))
                    return l.edi_format_id._l10n_mx_edi_get_invoice_cfdi_values(invoice)

    def get_ieps(self, tax_detail_vals):
        print("------------------------------------get_ieps-----------------------------------")
        print('tax_detail_vals', tax_detail_vals)
        print('tax_detail_vals.name', tax_detail_vals.name)
        print('tax_detail_vals.ieps', tax_detail_vals.ieps)

    def get_ieps_otro(self, values):
        print("-------------------------------------get_ieps_otro----------------------------------")
        print('values', values)
