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
class SaleOrder(models.Model):
    _inherit = "sale.order"
    
    @api.depends('order_line.price_total')
    def _amount_all(self):
        """
        Compute the total amounts of the SO.
        """
        if self.partner_id.show_ieps == True:
            return super(SaleOrder, self)._amount_all()
        else:
            for order in self:
                amount_untaxed = amount_tax = 0.0
                for line in order.order_line:
                    amount_untaxed += line.price_subtotal
                    amount_tax += line.price_total - line.price_subtotal
                order.update({
                    'amount_untaxed': amount_untaxed,
                    'amount_tax': amount_tax,
                    'amount_total': amount_untaxed + amount_tax,
                })

    def cal_taxs(self):
        for rec in self:
            rec.order_line._compute_tax_id()

