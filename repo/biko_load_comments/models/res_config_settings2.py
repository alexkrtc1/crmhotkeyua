# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    delay_alert_contract1 = fields.Integer(string='Delay alert contract outdated', config_parameter='biko_load_comments.delay_alert_contract1')

