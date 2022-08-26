# -*- coding: utf-8 -*-
from odoo import models, fields, api


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"   
    


    def _prepare_edi_vals_to_export(self):
        ''' The purpose of this helper is the same as '_prepare_edi_vals_to_export' but for a single invoice line.
        This includes the computation of the tax details for each invoice line or the management of the discount.
        Indeed, in some EDI, we need to provide extra values depending the discount such as:
        - the discount as an amount instead of a percentage.
        - the price_unit but after subtraction of the discount.

        :return: A python dict containing default pre-processed values.
        '''
        self.ensure_one()

        if self.move_id.partner_id.show_ieps == False:

            sub_total = 0
            for s in self.tax_ids:
                if s.ieps == False:
                    sub_total += ((self.price_unit * self.quantity) / ((s.amount / 100) + 1))

            if self.discount == 100.0:
                gross_price_subtotal = self.currency_id.round(self.price_unit * self.quantity)
            else:                    

                gross_price_subtotal = self.currency_id.round(sub_total / (1 - self.discount / 100.0))

            res = {
                'line': self,
                'price_unit_after_discount': self.currency_id.round(self.price_unit * (1 - (self.discount / 100.0))),
                'price_subtotal_before_discount': gross_price_subtotal,
                'price_subtotal_unit': self.currency_id.round(sub_total / self.quantity) if self.quantity else 0.0,
                'price_total_unit': self.currency_id.round(sub_total / self.quantity) if self.quantity else 0.0,
                'price_discount': gross_price_subtotal - sub_total,
                'price_discount_unit': (gross_price_subtotal - sub_total) / self.quantity if self.quantity else 0.0,
                'gross_price_total_unit': self.currency_id.round(gross_price_subtotal / self.quantity) if self.quantity else 0.0,
                'unece_uom_code': self.product_id.product_tmpl_id.uom_id._get_unece_code(),
            }
            return res
        else:

            if self.discount == 100.0:
                gross_price_subtotal = self.currency_id.round(self.price_unit * self.quantity)
            else:
                gross_price_subtotal = self.currency_id.round(self.price_subtotal / (1 - self.discount / 100.0))

            res = {
                'line': self,
                'price_unit_after_discount': self.currency_id.round(self.price_unit * (1 - (self.discount / 100.0))),
                'price_subtotal_before_discount': gross_price_subtotal,
                'price_subtotal_unit': self.currency_id.round(self.price_subtotal / self.quantity) if self.quantity else 0.0,
                'price_total_unit': self.currency_id.round(self.price_total / self.quantity) if self.quantity else 0.0,
                'price_discount': gross_price_subtotal - self.price_subtotal,
                'price_discount_unit': (gross_price_subtotal - self.price_subtotal) / self.quantity if self.quantity else 0.0,
                'gross_price_total_unit': self.currency_id.round(gross_price_subtotal / self.quantity) if self.quantity else 0.0,
                'unece_uom_code': self.product_id.product_tmpl_id.uom_id._get_unece_code(),
            }
            return res
