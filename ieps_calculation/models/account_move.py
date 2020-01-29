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

class AccountMoveLine(models.Model):
	_inherit = "account.move.line"

	# @api.model
	# def create(self, vals):
	# 	rec = super(AccountMoveLine, self).create(vals)
	# 	print("Move Line...")
	# 	if rec.product_id:
			# amount_ieps = 0
			# taxs = rec.product_id.taxes_id.filtered(lambda r: not rec.company_id or r.company_id == rec.company_id)
			# print("|||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||")
			# for x in taxs:
			# 	ieps = False
			# 	for z in x.tag_ids:
			# 		if z.name == 'IEPS':
			# 			ieps = True
			# 	if ieps == True:
			# 		if x.amount_type == 'fixed':
			# 			amount_ieps += x.amount * rec.quantity
			# 		if x.amount_type == 'percent':
			# 			amount_ieps += 78.37*(x.amount/100)
			# rec.credit = (100 - amount_ieps) * rec.quantity
		# return rec

	# @api.onchange("product_id")
	# def onchange_product_ieps(self):
		# print("|||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||")
		# if self.type in ('out_invoice', 'out_refund'):
		# amount_ieps = 0
		# taxs = self.product_id.taxes_id.filtered(lambda r: not self.company_id or r.company_id == self.company_id)
		# print("|||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||")
		# for x in taxs:
		# 	ieps = False
		# 	for z in x.tag_ids:
		# 		if z.name == 'IEPS':
		# 			ieps = True
		# 	if ieps == True:
		# 		if x.amount_type == 'fixed':
		# 			ieps_amount += x.amount * self.quantity
		# 		if x.amount_type == 'percent':
		# 			ieps_amount += 78.37*(x.amount/100)
		# self.credit = (100 - amount_ieps) * self.quantity