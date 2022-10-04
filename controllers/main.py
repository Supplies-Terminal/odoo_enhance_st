# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
import base64
import datetime
import json
import os
import logging
import re
import requests
import werkzeug.urls
import werkzeug.utils
import werkzeug.wrappers

from itertools import islice
from lxml import etree
from textwrap import shorten
from xml.etree import ElementTree as ET

import odoo

from odoo import http, models, fields, _
from odoo.http import request
from odoo.osv import expression
from odoo.tools import OrderedSet, escape_psql, html_escape as escape
from odoo.addons.http_routing.models.ir_http import slug, slugify, _guess_mimetype
from odoo.addons.portal.controllers.portal import pager as portal_pager
from odoo.addons.portal.controllers.web import Home

logger = logging.getLogger(__name__)

# Completely arbitrary limits
MAX_IMAGE_WIDTH, MAX_IMAGE_HEIGHT = IMAGE_LIMITS = (1024, 768)
LOC_PER_SITEMAP = 45000
SITEMAP_CACHE_TIME = datetime.timedelta(hours=12)

class Website(Home):

    @http.route('/purchasecard/<uuid>', type='http', auth="public", website=True, sitemap=True)
    def purchardcard(self, uuid, **kw):
        try:
            request.website.get_template('website.purchard_info').name
        except Exception as e:
            return request.env['ir.http']._handle_exception(e)
        
        # Module = request.env['st.purchasecard'].sudo()
        # purchaseCard = Module.search([('uuid', '=', uuid)])
        values = {
            'uuid': uuid,
        }
        return request.render('website.purchard_info', values)
