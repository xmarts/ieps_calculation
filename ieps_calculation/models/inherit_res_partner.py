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
    show_ieps = fields.Boolean(string="Mostrar IEPS (Factura cliente)", default=False)
