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
class ResPartner(models.Model):
	_inherit = "res.partner"
	show_ieps = fields.Boolean(string="Mostrar IEPS.", default=False)
		
class SaleOrderLine(models.Model):
	_inherit = 'sale.order.line'

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

	@api.multi
	@api.depends('tax_id')
	def _compute_tax_id(self):
		for line in self:
			if line.order_id.partner_id.show_ieps == True:
				fpos = line.order_id.fiscal_position_id or line.order_id.partner_id.property_account_position_id
				# If company_id is set, always filter taxes by the company
				taxes = line.product_id.taxes_id.filtered(lambda r: not line.company_id or r.company_id == line.company_id)
				line.tax_id = fpos.map_tax(taxes, line.product_id, line.order_id.partner_shipping_id) if fpos else taxes
			if line.order_id.partner_id.show_ieps == False:
				fpos = line.order_id.fiscal_position_id or line.order_id.partner_id.property_account_position_id
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

class InvoiceLines(models.Model):
	_inherit = "account.invoice.line"

	# @api.one
	# @api.depends('price_unit', 'discount', 'invoice_line_tax_ids', 'quantity',
	# 	'product_id', 'invoice_id.partner_id', 'invoice_id.currency_id', 'invoice_id.company_id',
	# 	'invoice_id.date_invoice', 'invoice_id.date')
	# def _compute_price(self):
	# 	if self.invoice_id.type not in ('out_invoice', 'out_refund'):
	# 		currency = self.invoice_id and self.invoice_id.currency_id or None
	# 		price = self.price_unit * (1 - (self.discount or 0.0) / 100.0)
	# 		taxes = False
	# 		if self.invoice_line_tax_ids:
	# 			taxes = self.invoice_line_tax_ids.compute_all(price, currency, self.quantity, product=self.product_id, partner=self.invoice_id.partner_id)
	# 		self.price_subtotal = price_subtotal_signed = taxes['total_excluded'] if taxes else self.quantity * price
	# 		self.price_total = taxes['total_included'] if taxes else self.price_subtotal
	# 		if self.invoice_id.currency_id and self.invoice_id.currency_id != self.invoice_id.company_id.currency_id:
	# 			currency = self.invoice_id.currency_id
	# 			date = self.invoice_id._get_currency_rate_date()
	# 			price_subtotal_signed = currency._convert(price_subtotal_signed, self.invoice_id.company_id.currency_id, self.company_id or self.env.user.company_id, date or fields.Date.today())
	# 		sign = self.invoice_id.type in ['in_refund', 'out_refund'] and -1 or 1
	# 		self.price_subtotal_signed = price_subtotal_signed * sign
	# 	if self.invoice_id.type in ('out_invoice', 'out_refund'):
	# 		currency = self.invoice_id and self.invoice_id.currency_id or None
	# 		price = self.price_unit * (1 - (self.discount or 0.0) / 100.0)
	# 		taxes = False
	# 		mytaxes = False
	# 		amount_ieps = 0
	# 		if self.invoice_line_tax_ids:
	# 			taxs = self.product_id.taxes_id.filtered(lambda r: not self.company_id or r.company_id == self.company_id)
	# 			lista = []
	# 			for x in taxs:
	# 				ieps = False
	# 				for z in x.tag_ids:
	# 					if z.name == 'IEPS':
	# 						ieps = True
	# 				if ieps == False:
	# 					lista.append(x.id)
	# 				else:
	# 					amount_ieps += x.amount
	# 			mytaxes = self.env['account.tax'].search([('id','in',lista)])
	# 			taxes = mytaxes.compute_all(price, currency, self.quantity, product=self.product_id, partner=self.invoice_id.partner_id)
	# 		#self.price_subtotal = price_subtotal_signed = taxes['total_excluded'] if taxes else self.quantity * price
	# 		self.price_subtotal = price_subtotal_signed = (self.price_unit * self.quantity)
	# 		self.price_total = (taxes['total_included'] if taxes else self.price_subtotal) + (amount_ieps*self.quantity)
	# 		if self.invoice_id.currency_id and self.invoice_id.currency_id != self.invoice_id.company_id.currency_id:
	# 			currency = self.invoice_id.currency_id
	# 			date = self.invoice_id._get_currency_rate_date()
	# 			price_subtotal_signed = currency._convert(price_subtotal_signed, self.invoice_id.company_id.currency_id, self.company_id or self.env.user.company_id, date or fields.Date.today())
	# 		sign = self.invoice_id.type in ['in_refund', 'out_refund'] and -1 or 1
	# 		self.price_subtotal_signed = price_subtotal_signed * sign



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

			amount_ieps = 0
			for x in taxes:
				ieps = False
				for z in x.tag_ids:
					if z.name == 'IEPS':
						ieps = True
				if ieps == True:
					amount_ieps += x.amount
			print("Factura-Impuestos ",taxes, lista)
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
					self.price_unit = self.price_unit * currency.with_context(dict(self._context or {}, date=self.invoice_id.date_invoice)).rate
		if self.invoice_id.type in ('out_invoice', 'out_refund'):

			company = self.invoice_id.company_id
			currency = self.invoice_id.currency_id
			if self.invoice_id.type in ('out_invoice', 'out_refund'):
				taxes = self.product_id.taxes_id or self.account_id.tax_ids or self.invoice_id.company_id.account_sale_tax_id
			else:
				taxes = self.product_id.supplier_taxes_id or self.account_id.tax_ids or self.invoice_id.company_id.account_purchase_tax_id
			taxes = taxes.filtered(lambda r: r.company_id == company)
			amount_ieps = 0
			for x in taxes:
				ieps = False
				for z in x.tag_ids:
					if z.name == 'IEPS':
						ieps = True
				if ieps == True:
					amount_ieps += x.amount
			if company and currency:
				self.price_unit = (self.price_unit * currency.with_context(dict(self._context or {}, date=self.invoice_id.date_invoice)).rate)




class AccountInvoice(models.Model):
	_inherit = "account.invoice"
	
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
				print("Lineas Analiticas: ", tax_ids)
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
				print("Lineas Analiticas: ", tax_ids)
				amount_ieps = 0
				taxs = line.product_id.taxes_id.filtered(lambda r: not self.company_id or r.company_id == self.company_id)
				lista = []
				for x in taxs:
					ieps = False
					for z in x.tag_ids:
						if z.name == 'IEPS':
							ieps = True
					if ieps == True:
						amount_ieps += x.amount
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
					res.append(move_line_dict)
			return res

	@api.multi
	def get_taxes_values(self):
		if self.type not in ('out_invoice', 'out_refund'):
			tax_grouped = {}
			round_curr = self.currency_id.round
			for line in self.invoice_line_ids:
				if not line.account_id:
					continue
				price_unit = line.price_unit * (1 - (line.discount or 0.0) / 100.0)
				taxes = line.invoice_line_tax_ids.compute_all(price_unit, self.currency_id, line.quantity, line.product_id, self.partner_id)['taxes']
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
		if self.type in ('out_invoice', 'out_refund'): 
			tax_grouped = {}
			round_curr = self.currency_id.round
			for line in self.invoice_line_ids:
				if not line.account_id:
					continue
				price_unit = line.price_unit * (1 - (line.discount or 0.0) / 100.0)
				amount_ieps = 0
				taxs = line.product_id.taxes_id.filtered(lambda r: not self.company_id or r.company_id == self.company_id)
				lista = []
				for x in taxs:
					ieps = False
					for z in x.tag_ids:
						if z.name == 'IEPS':
							ieps = True
					if ieps == True:
						amount_ieps += x.amount
				taxes = line.invoice_line_tax_ids.compute_all(price_unit, self.currency_id, line.quantity, line.product_id, self.partner_id)['taxes']
				for tax in taxes:
					val = self._prepare_tax_line_vals(line, tax)
					key = self.env['account.tax'].browse(tax['id']).get_grouping_key(val)
					if key not in tax_grouped:
						tax_grouped[key] = val
						tax_grouped[key]['base'] = round_curr(val['base'])
					else:
						tax_grouped[key]['amount'] += val['amount']
						tax_grouped[key]['base'] += round_curr(val['base'])
				if self.partner_id.show_ieps == False:
					taxs = line.product_id.taxes_id.filtered(lambda r: not self.company_id or r.company_id == self.company_id)
					lista = []
					for x in taxs:
						ieps = False
						for z in x.tag_ids:
							if z.name == 'IEPS':
								ieps = True
						if ieps == True:
							lista.append(x.id)
					mytaxes = self.env['account.tax'].search([('id','in',lista)])
					taxes = mytaxes.compute_all(price_unit, self.currency_id, line.quantity, line.product_id, self.partner_id)['taxes']
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

class AccountMoveLine(models.Model):
	_inherit = "account.move.line"

	@api.onchange("product_id")
	def _onchange_product_ieps(self):
		if self.type in ('out_invoice', 'out_refund'):
			amount_ieps = 0
			taxs = self.product_id.taxes_id.filtered(lambda r: not self.company_id or r.company_id == self.company_id)
			lista = []
			for x in taxs:
				ieps = False
				for z in x.tag_ids:
					if z.name == 'IEPS':
						ieps = True
				if ieps == True:
					amount_ieps += x.amount
			self.credit = (self.product_id.lst_price - amount_ieps) * self.quantity