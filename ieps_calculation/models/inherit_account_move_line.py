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
