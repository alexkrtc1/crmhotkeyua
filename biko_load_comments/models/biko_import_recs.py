from odoo import models, fields
import base64
import json
from datetime import datetime
import requests

class ImportRecs(models.TransientModel):
    _name = 'biko.import.recs'

    file = fields.Binary(string='File name')
    file_name = fields.Char()
    charset = fields.Selection(selection = [('UTF-8', 'UTF-8'), ('windows-1251', 'windows-1251')], string = 'Charset')

    def action_import_records(self):
        data = base64.b64decode(self.file)
        data = data.decode(self.charset)
        jsdata = json.loads(data)

        env_deals = self.env['crm.lead'].env

        for deal in jsdata.values():

            comments_list = deal['comments']
            # self.env.ref
            if not comments_list:
                continue

            external_id = deal['external_id']
            id = deal['id']

            # record = env_deals.ref('__import__.' + external_id)
            record = env_deals.ref(external_id)

            if record:
                for comment in comments_list.values():
                    date_time = datetime.fromisoformat(comment['CREATED']).replace(tzinfo=None)
                    msg = comment['COMMENT']
                    f_attachments = []
                    if ('FILES' in comment.keys()):
                        for c_file in comment['FILES'].values():
                            f_name = c_file['name']
                            req = requests.get(c_file['urlDownload'])
                            f_attachments.append((f_name, req.content))
                    message_rec = record.message_post(body=msg, message_type='comment', attachments=f_attachments)
                    message_rec['date'] = date_time
