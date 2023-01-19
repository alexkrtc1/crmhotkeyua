from odoo import fields, models, api

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    bitr_url = fields.Char(string="Bitrix Webhook Url")
    # allow_activity = fields.Boolean(string="Allow Import Planned Activity", config_parameter='biko_load_comments.allow_activity')
    allow_activity = fields.Boolean(string="Allow Import Planned Activity")

    # @api.model
    def get_values(self):
        ICP = self.env['ir.config_parameter'].sudo()
        res = super(ResConfigSettings, self).get_values()
        res['bitr_url'] = ICP.get_param('biko_load_comments.bitr_url', 'url')
        res['allow_activity'] = bool(ICP.get_param('biko_load_comments.allow_activity', False))
        print('get_values,')
        print(ICP.get_param('biko_load_comments.bitr_url'))
        return res

        # res = super(ResConfigSettings, self).get_values()
        # bitrix_url = self.env["ir.config_parameter"].sudo().get_param(
        #     "biko_load_comments.config.bitrix_url")
        # allow_planned_activity = bool(self.env['ir.config_parameter'].sudo().get_param(
        #     'biko_load_comments.config.allow_planned_activity'))
        # res.update({
        #     'bitrix_url': bitrix_url if type(bitrix_url) else False
        #     # 'allow_planned_activity': allow_planned_activity
        #     }
        # )
        # res['bitrix_url'] = bitrix_url
        # res['allow_planned_activity'] = allow_planned_activity
        # return res



    # @api.model
    def set_values(self):
        ICP = self.env['ir.config_parameter'].sudo()
        ICP.set_param('biko_load_comments.bitr_url', self.bitr_url)
        ICP.set_param('biko_load_comments.allow_activity', self.allow_activity)
        # super(ResConfigSettings, self).set_values()
        # res = super(ResConfigSettings, self).set_values()
        print('set_values')
        print(self.bitr_url)
        # IrDefault = self.env['ir.default'].sudo()
        # self.env['ir.config_parameter'].sudo().set_param(
        #     'biko_load_comments.config.bitrix_url', self.bitrix_url)
        # self.env['ir.config_parameter'].sudo().set_param(
        #     'biko_load_comments.config.allow_planned_activity', self.allow_planned_activity)
        # super(ResConfigSettings, self).set_values()
        # return res

        # super(ResConfigSettings, self).set_values()
        # IrDefault = self.env['ir.default'].sudo()
        # IrDefault.set('res.config.settings', 'biko_load_comments.config.bitrix_url', self.bitrix_url)
        # IrDefault.set('res.config.settings', 'biko_load_comments.config.allow_planned_activity', self.allow_planned_activity)
        # return True