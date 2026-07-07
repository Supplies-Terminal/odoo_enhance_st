# -*- coding: utf-8 -*-
from odoo import models


class ReplenishmentReport(models.AbstractModel):
    _inherit = 'report.stock.report_product_product_replenishment'

    def _exclude_unconfirmed_purchase_incoming_domain(self, in_domain):
        return in_domain + [
            '|',
            ('purchase_line_id', '=', False),
            ('purchase_line_id.order_id.state', 'in', ('purchase', 'done')),
        ]

    def _move_draft_domain(self, product_template_ids, product_variant_ids, wh_location_ids):
        in_domain, out_domain = super()._move_draft_domain(
            product_template_ids, product_variant_ids, wh_location_ids,
        )
        return self._exclude_unconfirmed_purchase_incoming_domain(in_domain), out_domain

    def _move_confirmed_domain(self, product_template_ids, product_variant_ids, wh_location_ids):
        in_domain, out_domain = super()._move_confirmed_domain(
            product_template_ids, product_variant_ids, wh_location_ids,
        )
        return self._exclude_unconfirmed_purchase_incoming_domain(in_domain), out_domain


class ReplenishmentTemplateReport(models.AbstractModel):
    _inherit = 'report.stock.report_product_template_replenishment'
