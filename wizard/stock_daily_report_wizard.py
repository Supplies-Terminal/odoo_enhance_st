# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models, api
from datetime import datetime, date, time, timedelta
import pytz

import logging
_logger = logging.getLogger(__name__)

class DailyStockReportWizard(models.TransientModel):
    _name = 'daily.stock.report.wizard'
    _description = 'daily stock report wizard'
    
    start_date = fields.Date('Start Date')
    end_date = fields.Date('End Date')

    @api.model
    def action_open_wizard(self):
        wizard = self.create({})
        return wizard._action_open_modal()

    def _action_open_modal(self):
        """Allow to keep the wizard modal open after executing the action."""
        self.refresh()
        return {
            'name': _('Generate the stock report'),
            'type': 'ir.actions.act_window',
            'res_model': 'daily.stock.report.wizard',
            'view_type': 'form',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
        }
        
    def action_generate_report(self):
        _logger.info("-------------- action_generate_report --------------------")
        """
        Generates the stock report for each day between the start_date and end_date.
        """
        date_from = self.start_date
        date_to = self.end_date
        if not date_from or not date_to:
            return {'warning': {
                'title': 'Date Error',
                'message': 'Both start and end dates must be set.'
            }}

        # 首先清空daily.stock.report中的所有数据
        self.env['daily.stock.report'].search([]).unlink()
        
        current_date = fields.Date.from_string(date_from)
        end_date = fields.Date.from_string(date_to)
        _logger.info(current_date)
        _logger.info(end_date)

        tz = pytz.timezone('America/Toronto')
        
        while current_date <= end_date:
            naive_datetime = datetime.combine(current_date, datetime.min.time())
            localized_datetime = tz.localize(naive_datetime, is_dst=None)
            date_utc = localized_datetime.astimezone(pytz.UTC)
            self.env['daily.stock.report'].calculate_stock_totals(date_utc)
            current_date += timedelta(days=1)

        # return {
        #     'type': 'ir.actions.client',
        #     'tag': 'display_notification',
        #     'params': {
        #         'title': 'Report Generated',
        #         'message': 'The stock report has been generated successfully.',
        #         'sticky': False,
        #     }
        # }
        # 返回客户端动作以刷新视图
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }