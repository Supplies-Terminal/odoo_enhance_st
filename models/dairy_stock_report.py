from odoo import models, fields, api
from datetime import timedelta
import logging
_logger = logging.getLogger(__name__)
from datetime import datetime, date, time, timedelta
import pytz

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

        date_str = date.strftime('%Y-%m-%d %H:%M:%S')
        _logger.info(date_str)

        products = self.env['product.product'].with_company(current_company_id).with_context(to_date=date_str).search([('type', '=', 'product')])
        total = sum(p.qty_available for p in products)

        self.create({'date': date, 'stock_total': total})
        
        return total

    @api.model
    def generate_report(self):
        # 首先清空daily.stock.report中的所有数据
        self.search([]).unlink()

        toronto_timezone = pytz.timezone('America/Toronto')
        now_utc = datetime.utcnow().replace(tzinfo=pytz.utc)
        now_toronto = now_utc.astimezone(toronto_timezone)
        end_datetime = toronto_timezone.localize(datetime(now_toronto.year, now_toronto.month, now_toronto.day, 23, 59, 59))
        
        # Logic to loop through the last 30 days and generate reports
        for day in range(0, 30):
            date = end_datetime - timedelta(days=day)
            date_utc = date.astimezone(pytz.UTC)
            total = self.calculate_stock_totals(date_utc)
            

    def daily_stock_report_wizard_action(self):
        self.env['daily.stock.report.wizard']._action_open_modal()
      