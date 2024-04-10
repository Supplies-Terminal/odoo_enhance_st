from odoo import models, fields, api
from datetime import timedelta
import logging
_logger = logging.getLogger(__name__)


class DailyStockReport(models.Model):
    _name = 'daily.stock.report'
    _description = 'Daily Stock Report'
    _rec_name = 'date'
    
    date = fields.Date(string='Date', required=True)
    stock_total = fields.Float(string='Stock Total')
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)
    
    @api.model
    def calculate_stock_totals(self, date):
        current_company_id = self.env.company.id
        _logger.info(current_company_id)

        date_str = fields.Date.to_string(date)
        _logger.info(date_str)

        products = self.env['product.product'].with_company(current_company_id).with_context(to_date=date_str).search([('type', '=', 'product')])
        total = sum(p.qty_available for p in products)

        return total

    @api.model
    def generate_report(self):
        # 首先清空daily.stock.report中的所有数据
        self.search([]).unlink()
    
        # Logic to loop through the last 30 days and generate reports
        for day in range(1, 31):
            date = fields.Date.today() - timedelta(days=day)
            total = self.calculate_stock_totals(date)
            self.create({'date': date, 'stock_total': total})