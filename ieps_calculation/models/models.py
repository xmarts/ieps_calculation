# -*- coding: utf-8 -*-
from collections import OrderedDict
import json
import re
import uuid
from functools import partial
from lxml import etree
from dateutil.relativedelta import relativedelta
from werkzeug.urls import url_encode
from odoo import api, exceptions, fields, models, _
from odoo.tools import email_re, email_split, email_escape_char, float_is_zero, float_compare, pycompat, date_utils
from odoo.tools.misc import formatLang
from odoo.exceptions import AccessError, UserError, RedirectWarning, ValidationError, Warning
from odoo.addons import decimal_precision as dp
import logging


class InvoiceLines(models.Model):
	_inherit = "account.invoice.line"

	def _set_taxes(self):
		""" Used in on_change to set taxes and price"""
		self.ensure_one()
		if self.invoice_id.type not in ('out_invoice', 'out_refund'):
			self.ensure_one()
			if self.invoice_id.type in ('out_invoice', 'out_refund'):
				taxes = self.product_id.taxes_id or self.account_id.tax_ids or self.invoice_id.company_id.account_sale_tax_id
			else:
				taxes = self.product_id.supplier_taxes_id or self.account_id.tax_ids or self.invoice_id.company_id.account_purchase_tax_id

			# Keep only taxes of the company
			company_id = self.company_id or self.env.user.company_id
			taxes = taxes.filtered(lambda r: r.company_id == company_id)

			self.invoice_line_tax_ids = fp_taxes = self.invoice_id.fiscal_position_id.map_tax(taxes, self.product_id, self.invoice_id.partner_id)

			fix_price = self.env['account.tax']._fix_tax_included_price
			if self.invoice_id.type in ('in_invoice', 'in_refund'):
				prec = self.env['decimal.precision'].precision_get('Product Price')
				if not self.price_unit or float_compare(self.price_unit, self.product_id.standard_price, precision_digits=prec) == 0:
					self.price_unit = fix_price(self.product_id.standard_price, taxes, fp_taxes)
					self._set_currency()
			else:
				self.price_unit = fix_price(self.product_id.lst_price, taxes, fp_taxes)
				self._set_currency()
		if self.invoice_id.type in ('out_invoice', 'out_refund'):
			self.ensure_one()
			if self.invoice_id.type in ('out_invoice', 'out_refund'):
				taxes = self.product_id.taxes_id or self.account_id.tax_ids or self.invoice_id.company_id.account_sale_tax_id
			else:
				taxes = self.product_id.supplier_taxes_id or self.account_id.tax_ids or self.invoice_id.company_id.account_purchase_tax_id
				

			# Keep only taxes of the company
			company_id = self.company_id or self.env.user.company_id
			taxes = taxes.filtered(lambda r: r.company_id == company_id)
			mytaxes = self.env['account.tax']

			lista = []
			for x in taxes:
				if self.partner_id.show_ieps == False:
					ieps = False
					for z in x.tag_ids:
						if z.name == 'IEPS':
							ieps = True
					if ieps == False:
						lista.append(x.id)
				else:
					lista.append(x.id)

			if self.invoice_id.type in ('in_invoice', 'in_refund'):
				self.invoice_line_tax_ids = fp_taxes = self.invoice_id.fiscal_position_id.map_tax(taxes, self.product_id, self.invoice_id.partner_id)
			else:
				self.invoice_line_tax_ids = fp_taxes = self.invoice_id.fiscal_position_id.map_tax(mytaxes.search([('id','in',lista)]), self.product_id, self.invoice_id.partner_id)

			fix_price = self.env['account.tax']._fix_tax_included_price
			fixx_price = mytaxes.search([('id','in',lista)])._fix_tax_included_price
			if self.invoice_id.type in ('in_invoice', 'in_refund'):
				prec = self.env['decimal.precision'].precision_get('Product Price')
				if not self.price_unit or float_compare(self.price_unit, self.product_id.standard_price, precision_digits=prec) == 0:
					self.price_unit = fix_price(self.product_id.standard_price, taxes, fp_taxes)
					self._set_currency()
			else:
				self.price_unit = fixx_price(self.product_id.lst_price, mytaxes.search([('id','in',lista)]), fp_taxes)
				self._set_currency()

	def _set_currency(self):
		if self.invoice_id.type not in ('out_invoice', 'out_refund'):
			company = self.invoice_id.company_id
			currency = self.invoice_id.currency_id
			if company and currency:
				if company.currency_id != currency:
					if self.invoice_id.tipo_cambio_manual != 0.0 and company.currency_id != currency:
						self.price_unit = (self.price_unit * self.invoice_id.tipo_cambio_manual)
					else:
						self.price_unit = (self.price_unit * currency.with_context(dict(self._context or {}, date=self.invoice_id.date_invoice)).rate)
		if self.invoice_id.type in ('out_invoice', 'out_refund'):

			company = self.invoice_id.company_id
			currency = self.invoice_id.currency_id
			if self.invoice_id.type in ('out_invoice', 'out_refund'):
				taxes = self.product_id.taxes_id or self.account_id.tax_ids or self.invoice_id.company_id.account_sale_tax_id
			else:
				taxes = self.product_id.supplier_taxes_id or self.account_id.tax_ids or self.invoice_id.company_id.account_purchase_tax_id
			taxes = taxes.filtered(lambda r: r.company_id == company)
			if company and currency:
				if self.invoice_id.tipo_cambio_manual != 0.0 and company.currency_id != currency:
					self.price_unit = (self.price_unit * self.invoice_id.tipo_cambio_manual)
				else:
					self.price_unit = (self.price_unit * currency.with_context(dict(self._context or {}, date=self.invoice_id.date_invoice)).rate)




class AccountInvoice(models.Model):
	_inherit = "account.invoice"

	tipo_cambio_manual = fields.Float(string="Defina el tipo de cambio manual.", digits=(12,6), help="Si quiere tomar el tipo de cambio por defecto deje el campo en cero '0.0'", default=0.0)
	
	def _amount_by_group(self):
		for invoice in self:
			currency = invoice.currency_id or invoice.company_id.currency_id
			fmt = partial(formatLang, invoice.with_context(lang=invoice.partner_id.lang).env, currency_obj=currency)
			res = {}
			taxs = []
			if invoice.partner_id.show_ieps == True:
				taxs = invoice.tax_line_ids
			else:
				for x in invoice.tax_line_ids:
					ieps = False
					for z in x.tax_id.tag_ids:
						if z.name == 'IEPS':
							ieps = True
					if ieps == False:
						taxs.append(x)
			for line in taxs:
				tax = line.tax_id
				group_key = (tax.tax_group_id, tax.amount_type, tax.amount)
				res.setdefault(group_key, {'base': 0.0, 'amount': 0.0})
				res[group_key]['amount'] += line.amount_total
				res[group_key]['base'] += line.base
			res = sorted(res.items(), key=lambda l: l[0][0].sequence)
			invoice.amount_by_group = [(
				r[0][0].name, r[1]['amount'], r[1]['base'],
				fmt(r[1]['amount']), fmt(r[1]['base']),
				len(res),
			) for r in res]

	@api.one
	@api.depends('invoice_line_ids.price_subtotal', 'tax_line_ids.amount', 'tax_line_ids.amount_rounding',
				 'currency_id', 'company_id', 'date_invoice', 'type')
	def _compute_amount(self):
		if self.type not in ('out_invoice', 'out_refund'):
			round_curr = self.currency_id.round
			self.amount_untaxed = sum(line.price_subtotal for line in self.invoice_line_ids)
			self.amount_tax = sum(round_curr(line.amount_total) for line in self.tax_line_ids)
			self.amount_total = self.amount_untaxed + self.amount_tax
			amount_total_company_signed = self.amount_total
			amount_untaxed_signed = self.amount_untaxed
			if self.currency_id and self.company_id and self.currency_id != self.company_id.currency_id:
				currency_id = self.currency_id
				amount_total_company_signed = currency_id._convert(self.amount_total, self.company_id.currency_id, self.company_id, self.date_invoice or fields.Date.today())
				amount_untaxed_signed = currency_id._convert(self.amount_untaxed, self.company_id.currency_id, self.company_id, self.date_invoice or fields.Date.today())
			sign = self.type in ['in_refund', 'out_refund'] and -1 or 1
			self.amount_total_company_signed = amount_total_company_signed * sign
			self.amount_total_signed = self.amount_total * sign
			self.amount_untaxed_signed = amount_untaxed_signed * sign
		if self.type in ('out_invoice', 'out_refund'):
			round_curr = self.currency_id.round
			self.amount_untaxed = sum(line.price_subtotal for line in self.invoice_line_ids)
			for line in self.tax_line_ids:
				if self.partner_id.show_ieps == True:
					self.amount_tax += round_curr(line.amount_total)
				else:
					if "IEPS" not in line.name.upper():
						self.amount_tax += round_curr(line.amount_total)
			# self.amount_tax = sum(round_curr(line.amount_total) for line in self.tax_line_ids)
			self.amount_total = round_curr(self.amount_untaxed + self.amount_tax)
			amount_total_company_signed = self.amount_total
			amount_untaxed_signed = self.amount_untaxed
			if self.currency_id and self.company_id and self.currency_id != self.company_id.currency_id:
				currency_id = self.currency_id
				amount_total_company_signed = currency_id._convert(self.amount_total, self.company_id.currency_id, self.company_id, self.date_invoice or fields.Date.today())
				amount_untaxed_signed = currency_id._convert(self.amount_untaxed, self.company_id.currency_id, self.company_id, self.date_invoice or fields.Date.today())
			sign = self.type in ['in_refund', 'out_refund'] and -1 or 1
			self.amount_total_company_signed = amount_total_company_signed * sign
			self.amount_total_signed = self.amount_total * sign
			self.amount_untaxed_signed = amount_untaxed_signed * sign		


	@api.model
	def invoice_line_move_line_get(self):
		if self.type not in ('out_invoice', 'out_refund'):
			res = []
			for line in self.invoice_line_ids:
				if not line.account_id:
					continue
				if line.quantity==0:
					continue
				tax_ids = []
				for tax in line.invoice_line_tax_ids:
					tax_ids.append((4, tax.id, None))
					for child in tax.children_tax_ids:
						if child.type_tax_use != 'none':
							tax_ids.append((4, child.id, None))
				analytic_tag_ids = [(4, analytic_tag.id, None) for analytic_tag in line.analytic_tag_ids]
				move_line_dict = {
					'invl_id': line.id,
					'type': 'src',
					'name': line.name,
					'price_unit': line.price_unit,
					'quantity': line.quantity,
					'price': line.price_subtotal,
					'account_id': line.account_id.id,
					'product_id': line.product_id.id,
					'uom_id': line.uom_id.id,
					'account_analytic_id': line.account_analytic_id.id,
					'analytic_tag_ids': analytic_tag_ids,
					'tax_ids': tax_ids,
					'invoice_id': self.id,
				}
				res.append(move_line_dict)
			return res
		if self.type in ('out_invoice', 'out_refund'):
			res = []
			for line in self.invoice_line_ids:
				if not line.account_id:
					continue
				if line.quantity==0:
					continue
				tax_ids = []
				for tax in line.invoice_line_tax_ids:
					tax_ids.append((4, tax.id, None))
					for child in tax.children_tax_ids:
						if child.type_tax_use != 'none':
							tax_ids.append((4, child.id, None))
				for tax in line.product_id.taxes_id:
					ieps = False
					for z in tax.tag_ids:
						if z.name == 'IEPS':
							ieps = True
					if ieps == True:
						tax_ids.append((4, tax.id, None))
				analytic_tag_ids = [(4, analytic_tag.id, None) for analytic_tag in line.analytic_tag_ids]
				amount_ieps = 0
				taxs = line.product_id.taxes_id.filtered(lambda r: not self.company_id or r.company_id == self.company_id)
				lista = []
				pricep = line.price_unit * (1 - (line.discount or 0.0) / 100.0)
				#taxes = line.tax_id.compute_all(price, line.order_id.currency_id, line.product_uom_qty, product=line.product_id, partner=line.order_id.partner_shipping_id)
				taxxs = False
				if self.partner_id.show_ieps == True:
					taxxs=line.invoice_line_tax_ids.filtered(lambda r: not self.company_id or r.company_id == self.company_id)
				else:
					taxxs=line.product_id.taxes_id.filtered(lambda r: not self.company_id or r.company_id == self.company_id)
				taxxes = taxxs.compute_all(pricep, self.currency_id, line.quantity, product=line.product_id, partner=self.partner_shipping_id)
				for x in taxxs:
					ieps = False
					for z in x.tag_ids:
						if z.name == 'IEPS':
							ieps = True
					if ieps == True:
						if x.amount_type == 'fixed':
							amount_ieps += x.amount * line.quantity
						if x.amount_type == 'percent':
							#Falta enviar precio unitario verdadero
							amount_ieps += taxxes['total_excluded']*(x.amount/100)
				if self.partner_id.show_ieps == True:
					move_line_dict = {
						'invl_id': line.id,
						'type': 'src',
						'name': line.name,
						'price_unit': line.price_unit,
						'quantity': line.quantity,
						'price': line.price_subtotal,
						'account_id': line.account_id.id,
						'product_id': line.product_id.id,
						'uom_id': line.uom_id.id,
						'account_analytic_id': line.account_analytic_id.id,
						'analytic_tag_ids': analytic_tag_ids,
						'tax_ids': tax_ids,
						'invoice_id': self.id,
					}
					# print("LINE1 :: ",move_line_dict)
					res.append(move_line_dict)
				else:
					move_line_dict = {
						'invl_id': line.id,
						'type': 'src',
						'name': line.name,
						'price_unit': line.price_unit,
						'quantity': line.quantity,
						'price': line.price_subtotal - (amount_ieps * line.quantity),
						'account_id': line.account_id.id,
						'product_id': line.product_id.id,
						'uom_id': line.uom_id.id,
						'account_analytic_id': line.account_analytic_id.id,
						'analytic_tag_ids': analytic_tag_ids,
						'tax_ids': tax_ids,
						'invoice_id': self.id,
					}
					# print("LINE2 :: ",move_line_dict)
					res.append(move_line_dict)
			return res


	@api.multi
	def get_taxes_values(self):
		rec = super(AccountInvoice, self).get_taxes_values()
		if self.partner_id.show_ieps == False:
			tax_grouped = {}
			round_curr = self.currency_id.round
			for line in self.invoice_line_ids:
				if not line.account_id:
					continue
				price_unit = line.price_unit * (1 - (line.discount or 0.0) / 100.0)
				taxes = line.product_id.taxes_id.compute_all(price_unit, self.currency_id, line.quantity, line.product_id, self.partner_id)['taxes']
				for tax in taxes:
					val = self._prepare_tax_line_vals(line, tax)
					key = self.env['account.tax'].browse(tax['id']).get_grouping_key(val)

					if key not in tax_grouped:
						tax_grouped[key] = val
						tax_grouped[key]['base'] = round_curr(val['base'])
					else:
						tax_grouped[key]['amount'] += val['amount']
						tax_grouped[key]['base'] += round_curr(val['base'])
			return tax_grouped
		else:
			return rec

	# @api.multi
	# def get_taxes_values(self):
	# 	if self.type not in ('out_invoice', 'out_refund'):
	# 		tax_grouped = {}
	# 		round_curr = self.currency_id.round
	# 		for line in self.invoice_line_ids:
	# 			if not line.account_id:
	# 				continue
	# 			price_unit = line.price_unit * (1 - (line.discount or 0.0) / 100.0)
	# 			taxes = line.invoice_line_tax_ids.compute_all(price_unit, self.currency_id, line.quantity, line.product_id, self.partner_id)['taxes']
	# 			for tax in taxes:
	# 				val = self._prepare_tax_line_vals(line, tax)
	# 				key = self.env['account.tax'].browse(tax['id']).get_grouping_key(val)

	# 				if key not in tax_grouped:
	# 					tax_grouped[key] = val
	# 					tax_grouped[key]['base'] = round_curr(val['base'])
	# 				else:
	# 					tax_grouped[key]['amount'] += val['amount']
	# 					tax_grouped[key]['base'] += round_curr(val['base'])
	# 		return tax_grouped
	# 	if self.type in ('out_invoice', 'out_refund'): 
	# 		tax_grouped = {}
	# 		round_curr = self.currency_id.round
	# 		for line in self.invoice_line_ids:
	# 			if not line.account_id:
	# 				continue
	# 			price_unit = line.price_unit * (1 - (line.discount or 0.0) / 100.0)
	# 			amount_ieps = 0
	# 			taxs = line.product_id.taxes_id.filtered(lambda r: not self.company_id or r.company_id == self.company_id)
	# 			lista = []
	# 			for x in taxs:
	# 				ieps = False
	# 				for z in x.tag_ids:
	# 					if z.name == 'IEPS':
	# 						ieps = True
	# 				if ieps == True:
	# 					amount_ieps += x.amount
	# 			taxes = line.invoice_line_tax_ids.compute_all(price_unit, self.currency_id, line.quantity, line.product_id, self.partner_id)['taxes']
	# 			for tax in taxes:
	# 				val = self._prepare_tax_line_vals(line, tax)
	# 				key = self.env['account.tax'].browse(tax['id']).get_grouping_key(val)
	# 				if key not in tax_grouped:
	# 					tax_grouped[key] = val
	# 					tax_grouped[key]['base'] = round_curr(val['base'])
	# 				else:
	# 					tax_grouped[key]['amount'] += val['amount']
	# 					tax_grouped[key]['base'] += round_curr(val['base'])
	# 			if self.partner_id.show_ieps == False:
	# 				taxs = line.product_id.taxes_id.filtered(lambda r: not self.company_id or r.company_id == self.company_id)
	# 				lista = []
	# 				for x in taxs:
	# 					ieps = False
	# 					for z in x.tag_ids:
	# 						if z.name == 'IEPS':
	# 							ieps = True
	# 					if ieps == True:
	# 						lista.append(x.id)
	# 				mytaxes = self.env['account.tax'].search([('id','in',lista)])
	# 				taxes = mytaxes.compute_all(price_unit, self.currency_id, line.quantity, line.product_id, self.partner_id)['taxes']
	# 				for tax in taxes:
	# 					val = self._prepare_tax_line_vals(line, tax)
	# 					key = self.env['account.tax'].browse(tax['id']).get_grouping_key(val)

	# 					if key not in tax_grouped:
	# 						tax_grouped[key] = val
	# 						tax_grouped[key]['base'] = round_curr(val['base'])
	# 					else:
	# 						tax_grouped[key]['amount'] += val['amount']
	# 						tax_grouped[key]['base'] += round_curr(val['base'])
	# 		return tax_grouped
