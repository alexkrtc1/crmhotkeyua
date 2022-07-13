from odoo import fields, models


class Company(models.Model):
    _inherit = 'res.company'

    # Add a new column to the res.company model,
    # stamp  image

    stamp_image = fields.Image(string="Stamp of company")


class Users(models.Model):
    _inherit = 'res.users'

    # Add a new column to the res.users model,
    # sign image
    sign_image = fields.Image(string="Personal signature")
