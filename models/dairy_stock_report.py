from odoo import models, fields

class DailyStockReport(models.Model):
    _name = 'daily.stock.report'
    _description = 'Daily Stock Report'
    _rec_name = 'date'
    
    date = fields.Date(string='Date', required=True)
    stock_total = fields.Float(string='Stock Total')
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)
    
    @api.model
    def calculate_stock_totals(self, date):
        # Example logic to calculate stock totals
        # This needs to be adjusted based on your specific requirements
        stock_quant = self.env['stock.quant'].search([('company_id', '=', self.env.user.company_id.id)])
        total = sum(quant.quantity for quant in stock_quant)
        return total

    @api.model
    def generate_report(self):
        # Logic to loop through the last 30 days and generate reports
        for day in range(1, 31):
            date = fields.Date.today() - timedelta(days=day)
            total = self.calculate_stock_totals(date)
            self.create({'date': date, 'stock_total': total})