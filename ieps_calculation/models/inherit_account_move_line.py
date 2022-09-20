# -*- coding: utf-8 -*-
from odoo import models, fields, api


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    def get_taxes_from_invoice_line(self, price_unit=None, quantity=None, discount=None, currency=None, product=None, partner=None, taxes=None, move_type=None):
        print("------------------------------------get_taxes_from_invoice_line-----------------------------------")
        self.ensure_one()
        print('self', self)
        taxes = self.get_taxes_from_invoice_line_model(
            price_unit=price_unit or self.price_unit,
            quantity=quantity or self.quantity,
            discount=discount or self.discount,
            currency=currency or self.currency_id,
            product=product or self.product_id,
            partner=partner or self.partner_id,
            taxes=taxes or self.tax_ids,
            move_type=move_type or self.move_id.move_type,
        )
        amount = 0
        if taxes:
            for item in taxes:
                tax = self.env['account.tax'].browse(item['id'])
                item.update({'ieps': tax.ieps})
                print('item', item)
                if not self.move_id.partner_id.show_ieps and tax.ieps:
                    amount += item.get('amount')
        print('amount', amount)
        return amount


    @api.model
    def get_taxes_from_invoice_line_model(self, price_unit, quantity, discount, currency, product, partner, taxes, move_type):
        print("------------------------------------otro_model-----------------------------------")
        res = {}
        # Compute 'price_subtotal'.
        line_discount_price_unit = price_unit * (1 - (discount / 100.0))
        subtotal = quantity * line_discount_price_unit
        if taxes:
            res = taxes._origin.with_context(force_sign=1).compute_all(line_discount_price_unit,
                quantity=quantity, currency=currency, product=product, partner=partner, is_refund=move_type in ('out_refund', 'in_refund'))
        return res.get('taxes') or False
    


    def _prepare_edi_vals_to_export(self):
        ''' The purpose of this helper is the same as '_prepare_edi_vals_to_export' but for a single invoice line.
        This includes the computation of the tax details for each invoice line or the management of the discount.
        Indeed, in some EDI, we need to provide extra values depending the discount such as:
        - the discount as an amount instead of a percentage.
        - the price_unit but after subtraction of the discount.

        :return: A python dict containing default pre-processed values.
        '''
        self.ensure_one()

        print("_prepare_edi_vals_to_export",self.move_id.partner_id.show_ieps)

        is_ieps = 0
        for s in self.tax_ids:
            if s.ieps == True:
                is_ieps += 1
        print("is_ieps",is_ieps)
        if is_ieps == 0:
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
        else:

            if self.move_id.partner_id.show_ieps == True:

                

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


                
            else:
                sub_total = 0
                for s in self.tax_ids:
                    if s.ieps == False:
                        sub_total += self.currency_id.round((self.price_unit * self.quantity) / ((s.amount / 100) + 1))

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
