# -*- coding: utf-8 -*-

from odoo import models, fields, api

# class ieps_calculation(models.Model):
#	 _name = 'ieps_calculation.ieps_calculation'

#	 name = fields.Char()
#	 value = fields.Integer()
#	 value2 = fields.Float(compute="_value_pc", store=True)
#	 description = fields.Text()
#
#	 @api.depends('value')
#	 def _value_pc(self):
#		 self.value2 = float(self.value) / 100

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
			for x in taxs:
				ieps = False
				for z in x.tag_ids:
					if z.name == 'IEPS':
						ieps = True
				if ieps == False:
					lista.append(x.id)
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

			self.price_unit = self.env['account.tax']._fix_tax_included_price_company(self._get_display_price(product), product.taxes_id, self.tax_id, self.company_id) + (tax_amount)

class InvoiceLines(models.Model):
	_inherit = "account.invoice.line"

	@api.one
	@api.depends('price_unit', 'discount', 'invoice_line_tax_ids', 'quantity',
		'product_id', 'invoice_id.partner_id', 'invoice_id.currency_id', 'invoice_id.company_id',
		'invoice_id.date_invoice', 'invoice_id.date')
	def _compute_price(self):
		currency = self.invoice_id and self.invoice_id.currency_id or None
		price = self.price_unit * (1 - (self.discount or 0.0) / 100.0)
		taxes = False
		mytaxes = False
		if self.invoice_line_tax_ids:
			taxs = self.invoice_line_tax_ids.filtered(lambda r: not self.company_id or r.company_id == self.company_id)
			lista = []
			for x in taxs:
				ieps = False
				for z in x.tag_ids:
					if z.name == 'IEPS':
						ieps = True
				if ieps == True:
					lista.append(x.id)
			mytaxes = self.env['account.tax'].search([('id','in',lista)])
			#taxes = mytaxes.compute_all(price, currency, self.quantity, product=self.product_id, partner=self.invoice_id.partner_id)
			taxes = self.invoice_line_tax_ids.compute_all(price, currency, self.quantity, product=self.product_id, partner=self.invoice_id.partner_id)
		self.price_subtotal = price_subtotal_signed = taxes['total_excluded'] if taxes else self.quantity * price
		amount_taxes = 0
		if mytaxes:
			for x in mytaxes:
				amount_taxes += x.amount
		print("amount_taxes ---------> ", amount_taxes)
		self.price_total = (taxes['total_included'] if taxes else self.price_subtotal) - amount_taxes
		if self.invoice_id.currency_id and self.invoice_id.currency_id != self.invoice_id.company_id.currency_id:
			currency = self.invoice_id.currency_id
			date = self.invoice_id._get_currency_rate_date()
			price_subtotal_signed = currency._convert(price_subtotal_signed, self.invoice_id.company_id.currency_id, self.company_id or self.env.user.company_id, date or fields.Date.today())
		sign = self.invoice_id.type in ['in_refund', 'out_refund'] and -1 or 1
		self.price_subtotal_signed = price_subtotal_signed * sign

class AccountInvoice(models.Model):
	_inherit = "account.invoice"
	
	@api.one
	@api.depends('invoice_line_ids.price_subtotal', 'tax_line_ids.amount', 'tax_line_ids.amount_rounding',
				 'currency_id', 'company_id', 'date_invoice', 'type')
	def _compute_amount(self):
		round_curr = self.currency_id.round
		self.amount_untaxed = sum(line.price_subtotal for line in self.invoice_line_ids)
		for line in self.tax_line_ids:
			if "IEPS" not in line.name.upper():
				self.amount_tax += round_curr(line.amount_total)
		#self.amount_tax = sum(round_curr(line.amount_total) for line in self.tax_line_ids)
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