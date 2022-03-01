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
        
class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    # @api.depends('product_uom_qty', 'discount', 'price_unit', 'tax_id')
    # def _compute_amount(self):
    #     """
    #     Compute the amounts of the SO line.
    #     """
    #     for line in self:
    #         price = line.price_unit * (1 - (line.discount or 0.0) / 100.0)
    #         taxes = line.tax_id.compute_all(price, line.order_id.currency_id, line.product_uom_qty, product=line.product_id, partner=line.order_id.partner_shipping_id)
    #         line.update({
    #             'price_tax': taxes['total_included'] - taxes['total_excluded'],
    #             'price_total': taxes['total_included'],
    #             'price_subtotal': taxes['total_excluded'],
    #         })
    #         if self.env.context.get('import_file', False) and not self.env.user.user_has_groups('account.group_account_manager'):
    #             line.tax_id.invalidate_cache(['invoice_repartition_line_ids'], [line.tax_id.id])

    @api.depends('product_uom_qty', 'discount', 'price_unit', 'tax_id')
    def _compute_amount(self):
        """
        Compute the amounts of the SO line.
        """
        for line in self:
            price = line.price_unit * (1 - (line.discount or 0.0) / 100.0)
            #taxes = line.tax_id.compute_all(price, line.order_id.currency_id, line.product_uom_qty, product=line.product_id, partner=line.order_id.partner_shipping_id)
            taxs = line.tax_id.filtered(lambda r: not line.company_id or r.company_id == line.company_id)
            lista = []
            ieps_amount = 0
            for x in taxs:
                ieps = False
                for z in x.tag_ids:
                    if z.name == 'IEPS':
                        ieps = True
                if ieps == False:
                    lista.append(x.id)
            for x in line.product_id.taxes_id:
                ieps = False
                for z in x.tag_ids:
                    if z.name == 'IEPS':
                        ieps = True
                if ieps == True:
                    ieps_amount += x.amount
            #price = price - ieps_amount
            mytaxes = self.env['account.tax'].search([('id','in',lista)])
            taxes = mytaxes.compute_all(price, line.order_id.currency_id, line.product_uom_qty, product=line.product_id, partner=line.order_id.partner_shipping_id)
            line.update({
                'price_tax': sum(t.get('amount', 0.0) for t in taxes.get('taxes', [])),
                'price_total': taxes['total_included'],
                'price_subtotal': taxes['total_excluded'],
            })

    # def _compute_tax_id(self):
    #     for line in self:
    #         line = line.with_company(line.company_id)
    #         fpos = line.order_id.fiscal_position_id or line.order_id.fiscal_position_id.get_fiscal_position(line.order_partner_id.id)
    #         # If company_id is set, always filter taxes by the company
    #         taxes = line.product_id.taxes_id.filtered(lambda t: t.company_id == line.env.company)
    #         line.tax_id = fpos.map_tax(taxes)

    def _compute_tax_id(self):
        for line in self:
            if line.order_id.partner_id.show_ieps == True:
                fpos = line.order_id.fiscal_position_id or line.order_id.partner_id.property_account_position_id
                # If company_id is set, always filter taxes by the company
                taxes = line.product_id.taxes_id.filtered(lambda r: not line.company_id or r.company_id == line.company_id)
                line.tax_id = fpos.map_tax(taxes, line.product_id, line.order_id.partner_shipping_id) if fpos else taxes
            if line.order_id.partner_id.show_ieps != True:
                print("TIENE ORDEN",line.order_id.partner_id.show_ieps)
                fpos = line.order_id.fiscal_position_id or line.order_id.partner_id.property_account_position_id
                print(fpos)
                # If company_id is set, always filter taxes by the company
                taxes = line.product_id.taxes_id.filtered(lambda r: not line.company_id or r.company_id == line.company_id)
                mytaxes = self.env['account.tax']
                lista = []
                for x in taxes:
                    ieps = False
                    for z in x.tag_ids:
                        if z.name == 'IEPS':
                            ieps = True
                    if ieps == False:
                        lista.append(x.id)
                
                line.tax_id = fpos.map_tax(mytaxes.search([('id','in',lista)]), line.product_id, line.order_id.partner_shipping_id) if fpos else taxes


    # @api.onchange('product_uom', 'product_uom_qty')
    # def product_uom_change(self):
    #     if not self.product_uom or not self.product_id:
    #         self.price_unit = 0.0
    #         return
    #     if self.order_id.pricelist_id and self.order_id.partner_id:
    #         product = self.product_id.with_context(
    #             lang=self.order_id.partner_id.lang,
    #             partner=self.order_id.partner_id,
    #             quantity=self.product_uom_qty,
    #             date=self.order_id.date_order,
    #             pricelist=self.order_id.pricelist_id.id,
    #             uom=self.product_uom.id,
    #             fiscal_position=self.env.context.get('fiscal_position')
    #         )
    #         self.price_unit = self.env['account.tax']._fix_tax_included_price_company(self._get_display_price(product), product.taxes_id, self.tax_id, self.company_id)
            
    @api.onchange('product_uom', 'product_uom_qty','tax_id')
    def product_uom_change(self):
        if not self.product_uom or not self.product_id:
            self.price_unit = 0.0
            return
        if self.order_id.pricelist_id and self.order_id.partner_id:
            product = self.product_id.with_context(
                lang=self.order_id.partner_id.lang,
                partner=self.order_id.partner_id,
                quantity=self.product_uom_qty,
                date=self.order_id.date_order,
                pricelist=self.order_id.pricelist_id.id,
                uom=self.product_uom.id,
                fiscal_position=self.env.context.get('fiscal_position')
            )
            iepstax = self.env['account.tax']
            lista2 = []
            for x in self.product_id.taxes_id:
                ieps = False
                for z in x.tag_ids:
                    if z.name == 'IEPS':
                        ieps = True
                if ieps == True:
                    lista2.append(x.id)
            tax_amount = 0
            for tax in iepstax.search([('id','in',lista2)]):
                tax_amount += tax.amount
            if self.order_id.partner_id.show_ieps == True:
                self.price_unit = (self.env['account.tax']._fix_tax_included_price_company(self._get_display_price(product), product.taxes_id, self.tax_id, self.company_id))
            else:
                self.price_unit = (self.env['account.tax']._fix_tax_included_price_company(self._get_display_price(product), product.taxes_id, self.tax_id, self.company_id)) + (tax_amount)
