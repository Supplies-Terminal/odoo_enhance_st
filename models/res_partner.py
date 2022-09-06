# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, api, fields, models, tools

class Partner(models.Model):
    _inherit = "res.partner"

    @api.model
    def name_get(self):
        res = []
        for rec in self:
            if (not rec.ref):
                res.append((rec.id, "%s (%s)" % (rec.name, rec.ref)))
            else:
                res.append((rec.id, "%s" % rec.name))
        return res

    @api.model
    def _name_search(self, name, args=None, operator='ilike', limit=100, name_get_uid=None):
        args = args or []

        if not (name == '' and operator == 'ilike'):
            args += ['|', (self._rec_name, operator, name), ('ref', operator, name)]
        return self._search(args, limit=limit, access_rights_uid=name_get_uid)
