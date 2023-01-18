from odoo import models, fields, api, _
import base64
import json
from datetime import datetime
import requests
from requests.structures import CaseInsensitiveDict
from datetime import timedelta
import csv
import yaml
import os
import re
from odoo.exceptions import UserError
from . import mail_tml
import urllib.parse
import logging


B24_URI = ''
# RESULT_FILE = ''
# SOURCE_FILE = ''
# CHARSET = ''
# contacts = None

relpath = os.path.dirname(os.path.realpath(__file__))
hk_logger = logging.getLogger(__name__)

with open(relpath + '/settings.yaml', 'r', encoding='UTF_8') as yaml_file:
    objects = yaml.load(yaml_file, yaml.Loader)
    B24_URI = objects['B24_WEBHOOK'] if objects['B24_WEBHOOK'][-1] != '/' else objects['B24_WEBHOOK'][0:-1]
    # RESULT_FILE = objects['RESULT_FILE']
    # SOURCE_FILE = objects['SOURCE_FILE']
    # CHARSET = objects['CHARSET']

headers = CaseInsensitiveDict()
headers["Content-Type"] = "application/json"




class ImportRecs(models.TransientModel):
    _name = 'biko.import.recs'

    file = fields.Binary(string='File name')
    file_name = fields.Char()
    charset = fields.Selection(selection=[('UTF-8', 'UTF-8'), ('windows-1251', 'windows-1251')], string='Charset')

    def common(self):
        pass

    def hello(self):
        deals = dict()
        selected = self.env.context["active_ids"]
        try:
        # ref = self.env['ir.model.data'].search([('name', '=', 'crm_lead_BXDeal_9382')])
            ref = self.env['ir.model.data'].search([('res_id','in',selected),('name', 'like', 'crm_lead_BXDeal_%'),('model','=','crm.lead')])

            for r in ref:
                ref_id = r.name.split('crm_lead_BXDeal_')[1]
                rname = r.name
                rmodule = r.module
                deals.update({ref_id: {'id': ref_id, 'external_id': rmodule+'.'+rname, 'comments': dict(), 'activities': dict()}})

            return deals

        except:
            print('Error dict deals')
            return dict()


        # >> > ref.res_id
        # 50
        # >> > ref_id = ref.res_id
        # >> > ref_id
        # 50
        # >> > self.env['crm.lead'].search([('id', '=', '27')])
        # crm.lead(27, )
        # >> > self.env['crm.lead'].search([('id', '=', ref_id)])
        # crm.lead(50, )
        # >> > lead = self.env['crm.lead'].search([('id', '=', ref_id)])




    # def get_deals(self):
    #     try:
    #         with open(SOURCE_FILE, 'r', encoding=CHARSET) as file:
    #
    #             deals = dict()
    #             csv_reader = csv.reader(file, delimiter=';')
    #
    #             firstline = True
    #
    #             for line in csv_reader:
    #
    #                 if firstline:
    #                     firstline = False
    #                     continue
    #
    #                 deals.update({line[0]: {'id': line[0], 'external_id': line[1], 'comments': dict()}})
    #
    #             return deals
    #
    #     except csv.Error as err:
    #         print(f'Error reading CSV file: {err}')
    #         return dict()
    #     except UnicodeDecodeError as err:
    #         print(f'Error reading CSV file: {err}')
    #         return dict()
    #     except IOError as err:
    #         print('Error working with file ' + SOURCE_FILE)
    #         print(err)


    def get_comments(self, deals):
        deals_with_files = {}

        templ_start = '{"halt":0,"cmd": {'
        templ_end = '}}'

        i = 0
        packages = []
        req_str = ""

        for deal in deals.values():

            req_str += f'"{deal["id"]}":"crm.timeline.comment.list?filter[ENTITY_ID]={deal["id"]}&filter[ENTITY_TYPE]=deal",'
            if ((i + 1) % 50 == 0) or (i == len(deals) - 1):
                json_res = json.loads(templ_start + req_str[0:-1] + templ_end)
                packages.append(json_res)
                req_str = ""
            i += 1

        packages = json.dumps(packages)

        for batch in packages:
            req = requests.post(f'{B24_URI}/batch', json=batch)

            if req.status_code != 200:
                print('Error accessing to B24!')
                continue

            resp_json = req.json()
            res_errors = resp_json['result']['result_error']
            res_comments = resp_json['result']['result']

            if len(res_errors) > 0:
                for key, val in res_errors.items():
                    print(key, ':', val['error_description'])

            if len(res_comments) > 0:
                for deal_id, comments in res_comments.items():
                    deal = deals[deal_id]
                    for comment_line in comments:
                        deal['comments'].update({comment_line['ID']: comment_line})
                        if 'FILES' in comment_line.keys():
                            for file in comment_line['FILES'].keys():
                                deals_with_files.update({file: {'deal_id': deal_id, 'comment_id': comment_line['ID']}})

                                file_id = {'id': file}
                                req_file = requests.post(f'{B24_URI}/disk.file.get', json=file_id)

                                if req_file.status_code != 200:
                                    print('Error accessing to file B24!')
                                    continue

                                resp_file_json = req_file.json()
                                # res_errors = resp_file_json['result']['result_error']
                                res_file = resp_file_json['result']

                                if len(res_file) > 0:
                                    deal['comments'][comment_line['ID']]['FILES'][file]['urlDownload'] = ''
                                    deal['comments'][comment_line['ID']]['FILES'][file]['urlDownload'] = res_file['DOWNLOAD_URL']

                                    # for c in deal['comments'].values():
                                    #     if 'FILES' in c.keys():
                                    #         for f in c['FILES']:
                                    #             DOWNLOAD_URL = f['urlDownload'];


        return [deals, deals_with_files]


    def get_activities(self,deals):

        for deal in deals.values():

            data_id = f'{{"filter": {{"OWNER_TYPE_ID": 2,"OWNER_ID": {deal["id"]} }}  ,"select":[ "*", "COMMUNICATIONS" ] }}'
            json_res = json.dumps(json.loads(data_id))
            req = requests.post(f'{B24_URI}crm.activity.list', headers=headers, data=json_res)
            # req = requests.post(f'{B24_URI}crm.activity.list', data=json_res)

            if req.status_code != 200:
                print('Error accessing to B24!')
                continue
            #
            resp_json = req.json()
            res_activity = resp_json['result']
            #
            if len(res_activity) > 0:
                for activity in res_activity:
                    deal = deals[activity['OWNER_ID']]
                    deal['activities'].update({activity['ID']: activity})
        return deals


    def get_username_activities(self,id):
            bitrix_user = {'lastname' : ''}
            data_id = f'{{"ID":{id}}}'
            json_res = json.dumps(json.loads(data_id))
            req = requests.post(f'{B24_URI}user.search', headers=headers, data=json_res)

            if req.status_code != 200:
                print('Error accessing to B24!')


            resp_json = req.json()
            res_users = resp_json['result']

            if len(res_users) > 0:
                for user in res_users:
                    bitrix_user['lastname'] = user['LAST_NAME']

            return bitrix_user


    def action_import_records(self):
        # deals = self.get_deals()
        deals = self.hello()
        if len(deals) == 0:
            print('Error while loading deals!')
            return

        deals_res, deals_with_files = self.get_comments(deals)
        deals_res = self.get_activities(deals_res)

        # for i_id, i_comments in deals_res.items():
        #     if i_comments['comments']:
        #         for c_id, c_comments in i_comments['comments'].items():
        #              if c_comments['COMMENT']=="":
        #                 print('empty')


        env_deals = self.env['crm.lead'].env

        for deal in deals_res.values():

            comments_list = deal['comments']
            activity_list = deal['activities']

            external_id = deal['external_id']
            id = deal['id']
            # user_id = self.env['res.users'].search(['id', '=', 11])
            # record = env_deals.ref('__import__.' + external_id)
            record = env_deals.ref(external_id)
            #
            if record:
                if comments_list:
                    for comment in comments_list.values():
                        date_time = datetime.fromisoformat(comment['CREATED']).replace(tzinfo=None)
                        msg = comment['COMMENT']
                        f_attachments = []
                        if ('FILES' in comment.keys()):
                            for c_file in comment['FILES'].values():
                                f_name = c_file['name']
                                req = requests.get(c_file['urlDownload'])
                                # req = requests.get('https://asoft.bitrix24.ua/rest/178/jimsij9n3h1qe5ol/download/?token=disk%7CaWQ9MTA4NDczJl89V05kdkNhRG1kNVBra3ZLNEljTVFUVEZDdE01UjZTN1o%3D%7CImRvd25sb2FkfGRpc2t8YVdROU1UQTRORGN6Smw4OVYwNWtka05oUkcxa05WQnJhM1pMTkVsalRWRlVWRVpEZEUwMVVqWlROMW89fDE3OHxqaW1zaWo5bjNoMXFlNW9sIg%3D%3D.egSeeSNXPhvk1wpNPqy9fPiw3wgYzkggAipQ29XoR0k%3D')
                                f_attachments.append((f_name, req.content))
                        message_rec = record.message_post(body=msg, message_type='comment', attachments=f_attachments)
                        message_rec['date'] = date_time

                if activity_list:
                    for activity in activity_list.values():
                        author_id = activity['AUTHOR_ID']
                        dict_user = self.get_username_activities(author_id)
                        user_id = self.env['res.users'].search([('name', 'like', dict_user['lastname'])]).id
                        if not user_id:
                            user_id = self.env.uid

                        date_deadline = datetime.fromisoformat(activity['DEADLINE']).replace(tzinfo=None)
                        # date_deadline = fields.Datetime.now()+timedelta(days=1)
                        # date_deadline = fields.Date.context_today(self)
                        note = activity['SUBJECT']

                        if (activity['PROVIDER_TYPE_ID'] == "CALL"):
                            activity_typ = 'mail.mail_activity_data_call'
                        else:
                            activity_typ = None


                        act_env = record.activity_schedule(activity_typ,user_id=user_id,date_deadline=date_deadline,summary=note, note=note)
                        # act_env.action_feedback(feedback='ok')


        # data = base64.b64decode(self.file)
        # data = data.decode(self.charset)
        # jsdata = json.loads(data)
        #
        # env_deals = self.env['crm.lead'].env
        #
        # for deal in jsdata.values():
        #
        #     comments_list = deal['comments']
        #     # self.env.ref
        #     if not comments_list:
        #         continue
        #
        #     external_id = deal['external_id']
        #     id = deal['id']
        #     user_id = self.env['res.users'].search(['id', '=', 11])
        #     # record = env_deals.ref('__import__.' + external_id)
        #     record = env_deals.ref(external_id)
        #
        #     if record:
        #         for comment in comments_list.values():
        #             date_time = datetime.fromisoformat(comment['CREATED']).replace(tzinfo=None)
        #             msg = comment['COMMENT']
        #             f_attachments = []
        #             if ('FILES' in comment.keys()):
        #                 for c_file in comment['FILES'].values():
        #                     f_name = c_file['name']
        #                     req = requests.get(c_file['urlDownload'])
        #                     f_attachments.append((f_name, req.content))
        #             message_rec = record.message_post(body=msg, message_type='comment', attachments=f_attachments)
        #             message_rec['date'] = date_time


class ImportComments(models.Model):
    _inherit = 'crm.lead'

    partner_company = mail_tml.partner_company
    date_deadline_tml = mail_tml.date_deadline_tml
    communication_name_tml = mail_tml.communication_name_tml
    company_tml = mail_tml.company_tml
    responsible_user_tml = mail_tml.responsible_user_tml
    # contacts = None

    def test(self):
        a=1
        b=3
        print(a+b)

    def hello(self):
        deals = dict()
        selected = self.env.context["active_ids"]
        try:
        # ref = self.env['ir.model.data'].search([('name', '=', 'crm_lead_BXDeal_9382')])
            ref = self.env['ir.model.data'].search([('res_id','in',selected),('name', 'like', 'crm_lead_BXDeal_%'),('model','=','crm.lead')])

            for r in ref:
                ref_id = r.name.split('crm_lead_BXDeal_')[1]
                rname = r.name
                rmodule = r.module
                deals.update({ref_id: {'id': ref_id, 'external_id': rmodule+'.'+rname, 'comments': dict(), 'activities': dict()}})

            return deals

        except:
            print('Error dict deals')
            return dict()


    def get_comments(self, deals):
        deals_with_files = {}

        templ_start = '{"halt":0,"cmd": {'
        templ_end = '}}'

        i = 0
        packages = []
        req_str = ""

        for deal in deals.values():

            req_str += f'"{deal["id"]}":"crm.timeline.comment.list?filter[ENTITY_ID]={deal["id"]}&filter[ENTITY_TYPE]=deal",'
            if ((i + 1) % 50 == 0) or (i == len(deals) - 1):
                json_res = json.loads(templ_start + req_str[0:-1] + templ_end)
                packages.append(json_res)
                req_str = ""
            i += 1


        for batch in packages:
            req = requests.post(f'{B24_URI}/batch', json=batch)

            if req.status_code != 200:
                print('Error accessing to B24!')
                continue

            resp_json = req.json()
            res_errors = resp_json['result']['result_error']
            res_comments = resp_json['result']['result']

            if len(res_errors) > 0:
                for key, val in res_errors.items():
                    print(key, ':', val['error_description'])

            if len(res_comments) > 0:
                for deal_id, comments in res_comments.items():
                    deal = deals[deal_id]
                    for comment_line in comments:
                        deal['comments'].update({comment_line['ID']: comment_line})
                        if 'FILES' in comment_line.keys():
                            for file in comment_line['FILES'].keys():
                                deals_with_files.update({file: {'deal_id': deal_id, 'comment_id': comment_line['ID']}})

                                file_id = {'id': file}
                                req_file = requests.post(f'{B24_URI}/disk.file.get', json=file_id)

                                if req_file.status_code != 200:
                                    print('Error accessing to file B24!')
                                    continue

                                resp_file_json = req_file.json()
                                # res_errors = resp_file_json['result']['result_error']
                                res_file = resp_file_json['result']

                                if len(res_file) > 0:
                                    deal['comments'][comment_line['ID']]['FILES'][file]['urlDownload'] = ''
                                    deal['comments'][comment_line['ID']]['FILES'][file]['urlDownload'] = res_file['DOWNLOAD_URL'];

                                    # for c in deal['comments'].values():
                                    #     if 'FILES' in c.keys():
                                    #         for f in c['FILES']:
                                    #             DOWNLOAD_URL = f['urlDownload'];


        return [deals, deals_with_files]


    def get_activities(self,deals):

        for deal in deals.values():
            # COMPLETED
            allow_planned_activity = bool(self.env['ir.config_parameter'].sudo().get_param('biko_load_comments.allow_activity'))
            if allow_planned_activity:
                data_id = f'{{"filter": {{"OWNER_TYPE_ID": 2,"OWNER_ID": {deal["id"]} }}  ,"select":[ "*", "COMMUNICATIONS" ] }}'
            else:
                data_id = f'{{"filter": {{"OWNER_TYPE_ID": 2,"OWNER_ID": {deal["id"]},"COMPLETED":"YES" }}  ,"select":[ "*", "COMMUNICATIONS" ] }}'
            json_res = json.dumps(json.loads(data_id))
            req = requests.post(f'{B24_URI}/crm.activity.list', headers=headers, data=json_res)
            # req = requests.post(f'{B24_URI}crm.activity.list', data=json_res)

            if req.status_code != 200:
                print('Error accessing to B24!')
                continue
            #
            resp_json = req.json()
            res_activity = resp_json['result']
            #
            if len(res_activity) > 0:
                for activity in res_activity:
                    deal = deals[activity['OWNER_ID']]
                    deal['activities'].update({activity['ID']: activity})
        return deals


    def get_username_activities(self):
            bitrix_user = {'lastname' : ''}
            # data_id = f'{{"ID":{id}}}'
            # json_res = json.dumps(json.loads(data_id))
            # req = requests.post(f'{B24_URI}/user.search', headers=headers, data=json_res)
            # req = requests.post(f'{B24_URI}/user.get', headers=headers, data=json_res)
            req = requests.post(f'{B24_URI}/user.get', headers=headers)

            if req.status_code != 200:
                print('Error accessing to B24!')

            resp_json = req.json()
            res_users = resp_json['result']

            # if len(res_users) > 0:
            #     res = next((user for user in res_users if user['ID']==id), False)
            #     if res:
            #         bitrix_user['lastname'] = res['LAST_NAME']
            return res_users

    def post_from_url(self, url, param, pheaders=headers):
        req = requests.post(url, param, headers=pheaders)

        if req.status_code != 200:
            print('Error accessing to B24!')

        resp_json = req.json()
        res = resp_json['result']
        start = resp_json['next']
        total = resp_json['total']
        quant_url_items = int(total / start)
        start_page = 0
        templ_start = '{"halt":0,"cmd": {'
        templ_end = '}}'
        packages = []
        param_str = ''
        i = 1

        # param_dict = json.loads(param)
        # for s in range(50, total,50):
        #     param_dict.update({"start": s})
        #     # param_str = json.dumps(param_dict)
        #     # param_str += '"'+str(s)+'":"' + url + '/?' + urllib.parse.urlencode(param_dict)  +'",'
        #     param_str += '"'+str(s)+'":"' + url + '/?' + param_dict  +'",'
        #     if ((i % 50 == 0) or (s == quant_url_items * start)):
        #         param_dict = json.loads(templ_start + param_str[0:-1] + templ_end)
        #         packages.append(param_dict)
        #         param_str = ""
        #     i += 1
        #     print(s)

        # for s in range(50, total, 50):
        #     # param_dict.update({"start": s})
        #     param_str += '"'+str(s)+'":"' + url + '?' + param.format(s=s) + '",'
        #     if ((i % 50 == 0) or (s == quant_url_items * start)):
        #         param_dict = json.loads(templ_start + param_str[0:-1] + templ_end)
        #         packages.append(param_dict)
        #         param_str = ""
        #     i += 1
        # https://asoft.bitrix24.ua/rest/178/in25s0uxw7tr0dnh/crm.contact.list?order[DATE_CREATE]=ASC&select=ID&select=NAME&select=LAST_NAME&select=LEAD_ID&select=COMPANY_ID&select=EMAIL&select=PHONE&select=TYPE_ID&start=50
        # for batch in packages:
        #     req = requests.post(f'{B24_URI}/batch', json=batch)
        #     if req.status_code != 200:
        #         print('Error accessing to B24!')
        #         continue
        #
        #     resp_json = req.json()
        #     res.extend(resp_json['result'])
        #

        param_dict = json.loads(param)
        #https://asoft.bitrix24.ua/rest/178/in25s0uxw7tr0dnh/crm.contact.list?order=%7B%27DATE_CREATE%27%3A+%27ASC%27%7D&select=%5B%27ID%27%2C+%27NAME%27%2C+%27LAST_NAME%27%2C+%27LEAD_ID%27%2C+%27COMPANY_ID%27%2C+%27EMAIL%27%2C+%27PHONE%27%2C+%27TYPE_ID%27%5D&start=50
        # "https://asoft.bitrix24.ua/rest/178/in25s0uxw7tr0dnh/crm.contact.list?order[DATE_CREATE]=ASC&select=ID,NAME,LAST_NAME,LEAD_ID,COMPANY_ID,EMAIL,PHONE,TYPE_ID&start=50"
        while 'next' in resp_json:
            start_page += start
            param_dict.update({"start": start_page})
            param_str = json.dumps(param_dict,ensure_ascii=False)
            req = requests.post(url, param_str, headers=pheaders)
            resp_json = req.json()
            res.extend(resp_json['result'])
            i += 1

        hk_logger.info("contacts loops%s", i)
        return res

        ######

    # def get_comments(self, deals):
    #     deals_with_files = {}
    #
    #     templ_start = '{"halt":0,"cmd": {'
    #     templ_end = '}}'
    #
    #     i = 0
    #     packages = []
    #     req_str = ""
    #
    #     for deal in deals.values():
    #
    #         req_str += f'"{deal["id"]}":"crm.timeline.comment.list?filter[ENTITY_ID]={deal["id"]}&filter[ENTITY_TYPE]=deal",'
    #         if ((i + 1) % 50 == 0) or (i == len(deals) - 1):
    #             json_res = json.loads(templ_start + req_str[0:-1] + templ_end)
    #             packages.append(json_res)
    #             req_str = ""
    #         i += 1
    #
    #     for batch in packages:
    #         req = requests.post(f'{B24_URI}/batch', json=batch)
    #
    #         if req.status_code != 200:
    #             print('Error accessing to B24!')
    #             continue
    #
    #         resp_json = req.json()
    #         res_errors = resp_json['result']['result_error']
    #         res_comments = resp_json['result']['result']
    #
    #         if len(res_errors) > 0:
    #             for key, val in res_errors.items():
    #                 print(key, ':', val['error_description'])

    ##########

    def action_import_records(self):
        # deals = self.get_deals()
        deals = self.hello()
        if len(deals) == 0:
            print('Error while loading deals!')
            return

        deals_res, deals_with_files = self.get_comments(deals)
        deals_res = self.get_activities(deals_res)

        env_deals = self.env['crm.lead'].env
        odoobot_id = self.env['ir.model.data'].xmlid_to_res_id("base.partner_root")

        for deal in deals_res.values():

            comments_list = deal['comments']
            # activity_list = deal['activities']

            external_id = deal['external_id']
            id = deal['id']
            # user_id = self.env['res.users'].search(['id', '=', 11])
            # record = env_deals.ref('__import__.' + external_id)
            record = env_deals.ref(external_id)
            #
            if record:
                if comments_list:
                    dict_users = self.get_username_activities()

                    for comment in comments_list.values():
                        date_time = datetime.fromisoformat(comment['CREATED']).replace(tzinfo=None)
                        msg = comment['COMMENT']
                        f_attachments = []
                        if ('FILES' in comment.keys()):
                            for c_file in comment['FILES'].values():
                                f_name = c_file['name']
                                req = requests.get(c_file['urlDownload'])
                                # req = requests.get('https://asoft.bitrix24.ua/rest/178/jimsij9n3h1qe5ol/download/?token=disk%7CaWQ9MTA4NDczJl89V05kdkNhRG1kNVBra3ZLNEljTVFUVEZDdE01UjZTN1o%3D%7CImRvd25sb2FkfGRpc2t8YVdROU1UQTRORGN6Smw4OVYwNWtka05oUkcxa05WQnJhM1pMTkVsalRWRlVWRVpEZEUwMVVqWlROMW89fDE3OHxqaW1zaWo5bjNoMXFlNW9sIg%3D%3D.egSeeSNXPhvk1wpNPqy9fPiw3wgYzkggAipQ29XoR0k%3D')
                                f_attachments.append((f_name, req.content))

                        author_id = comment['AUTHOR_ID']
                        if len(dict_users) > 0:
                            res_user = next((user for user in dict_users if user['ID'] == author_id), False)

                        if res_user:
                            user_search = self.env['res.users'].search([('name', 'like', res_user['LAST_NAME'])])
                            if user_search:
                                user_id = user_search[0].partner_id.id
                            else:
                                user_id = odoobot_id
                        message_rec = record.message_post(body=msg, author_id=user_id, message_type='comment', attachments=f_attachments)
                        message_rec['date'] = date_time


                # if activity_list:
                #     for activity in activity_list.values():
                #         author_id = activity['AUTHOR_ID']
                #         dict_user = self.get_username_activities(author_id)
                #         user_id = self.env['res.users'].search([('name', 'like', dict_user['lastname'])]).id
                #         if not user_id:
                #             user_id = self.env.uid
                #
                #         date_deadline = datetime.fromisoformat(activity['DEADLINE']).replace(tzinfo=None)
                #         # date_deadline = fields.Datetime.now()+timedelta(days=1)
                #         # date_deadline = fields.Date.context_today(self)
                #         note = activity['SUBJECT']
                #
                #         if (activity['PROVIDER_TYPE_ID'] == "CALL"):
                #             activity_typ = 'mail.mail_activity_data_call'
                #         else:
                #             activity_typ = None
                #
                #         act_env = record.activity_schedule(activity_typ, user_id=user_id, date_deadline=date_deadline,
                #                                            summary=note, note=note)
                #         # act_env.action_feedback(feedback='ok')


    def action_import_activities(self):
        # url = "https://asoft.bitrix24.ua/bitrix/tools/crm_show_file.php?fileId=244574&ownerTypeId=6&ownerId=175130&auth="
        # headers = CaseInsensitiveDict()
        # headers["authority"] = "asoft.bitrix24.ua"
        # headers["accept"] = "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9"
        # headers["accept-language"] = "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7"
        # headers["cookie"] = "USER_LANG=ua; BITRIX_SM_UIDL=alexkrtcukr%40hotkey.ua; BITRIX_SM_CC=Y; BX_USER_ID=d06c0a50e923200df548469bde8bad59; BITRIX_SM_SALE_UID=46; BITRIX_SM_TZ=Europe/Kiev; BITRIX_SM_UIDH=iSTjY0ZSIifCRuAGh5HINOjf1AassDtz; BITRIX_SM_kernel=-crpt-kernel_0; BITRIX_SM_PK=%2F1068%2Fbfd3b4cf86f9969167f1255b4f53d9d1; BITRIX_SM_SOUND_LOGIN_PLAYED=Y; PHPSESSID=Qkk7Tnut7rrjV5jpFL6eK0E001xeYYQf; qmb=1068.socservices.1; BITRIX_SM_kernel_0=0R8LTQwnElSKMcMzWQTgc0liCqBpMe28ut8LrNk5tGH8GfNsK0zvlKiER4PFOCOXYi1gLQ3f57z1uEaXo2tQGDH2537oTjo0nIL9U3ZUfZ3GhRB1zA3Ot3xb-EVKD_R81FvHiQtgsuNRKYvF8UKS__6bXlaQas0poXPIHVZ8NmdPBl2mlGcpCmKcRfdCrzuYvaFYd7N6B3e7mYJ8ODf_Ab6YdMvOkLz9iJ0bDJUP46KiSj8O_j_zNvEHphlaPM-GfxhKdpO9Jy_nEzacDJVHneBE8K7PaTcwv4q-6h_F1VaL_vVzNEdrW7HP1yL-4_XtGIbebd9KVrB9IM6oID4Uu-4xs-4Pb5D-g3q4aO_p9VuSNjEzJERpHF6DmPVxPCRj_fAttJnhNDDmBXRf125LVwFnXHNjqNZmi-N1lVf0CjvYArN1qhsxnAY56sqf-SbdPEZn9zu9H-tf8D_FxKHQGRbDNoelcwN5xO04DVsnq2UYUSTygCB_KbY7fywVi0g8gPqCghILJUNdSU65oUEWiPurVTj-nSjr6s3gdO-ZOFoPgGXecOo7RYkGCRqyrvOyTtb0sr7OUysxzRIz_V18BMrTlBaJAO9tw_fIhaKS5sBq-BtLROeFUBu_B4wT45p6oKR-fOU94K8Qd5iKZfrXlxZgsRuSa1DJFRNZ1VcTNYkhjcKHWzKz51yPyV7SovYrSg_luu8avrEoem5bIk1TsCIuk3TXgzBqyiiK6aZX2JotcLmCA_bp2Sdvaz-OY8So3cadpKXciYD5Q8l3c-sAIazhHZA0XtAJ-VIBwTQRTBitZkzKM-VgMS_x5TOY3KUSP4QeinY4T56C-Bmvg9rz4GgWE0P9bk6w1Zc6XzTyJbfdce78wJtG1do57UKWteyYdPwpL7rkAvJfOBkRdBx5eOH7vtq29QfLFxY42S7qKx-YMZwyQ8ePy8Kj8e37t4ZlTUIwg_gKjSSq1mvpXbPvRejHhZrtt8_0L3faYvjqNMG4NnNfcMMy2ohDpAE_ePYlJKiJuz0B8zadiJyqFH2pLX64hVMY7myjDBfVhoiB00AUvAEtuFwxScqv5hnSUorK1qBbFsUCER8FApU6BwlVaJf0yyK_ICnlbb-ObeBOL7VtlduIYLqGLY6tHjzCwgB1ErsNO-qDzDmx1a9_0UaGnamRhpT6GRFbxYrMstL26MDj62V1w2yknZZtFJjIyY_8lg3UUwdONh3MESbUL3wKxtox4Eblrff6tn4pYGd-cufDrQsqoM7r0jU46uy2QdS3lYaoe-CHDtaGcg-8nLz0s72qmef10bOd-qBD8suhk9dJ08tBSDnDlrTNtySFqkScpmCPnindrYOC4vwhKUic7kKoHs8_4I0C5eRAz61heEDJ20P7NEkhvwPkBVzT_yOE4th5Vk-uTlH4ZIIvLMI2cG4-NNWKFEcWS2TMWIEnwBSWYnI5jP5z6bgdHredXAH7UK6A_MMiYWhMgmCSb6scqJ3yOXjvF11pUoJMJkX-5QTNrSdt3-TguBPWBl1lfUROK9i6b1yRKdqAi537_yYFKoGo-q7DAx70SxFb4kOs1ohqbhP7AeRyIi3cUIsfH_Z3znFIQJNen7M9hutpfES-TixdtqR62PD09KRjC8pbnZd19K1d6RmJojYEemeliov5-qQ4mUB3_sOdC5QfBcAyQ9HFuz75ElYfsu4xSRNNRjuyEtVg1gvo5umn8kmENbdnv6BvoUz9ZnYukj8o2Jq_h3hbi8AcCbtR_M4qcmg2inbJg2Dhdx3akLWS_h9WdXk24o107Po6VFwGJZSelL1F6DuF1EnTXN0rfV5W62c0D5H0lwlVmqpR3Z9UIabLAe8OCFCwSp8obg3QcMIn5ga9KjM7PQwHHuoZhqO3EoaGU4Q"
        # headers["if-modified-since"] = "Thu, 21 Jul 2022 14:28:20 GMT"
        # headers["if-none-match"] = '"4a85b362d3ac20ff75d023aaadcba96e"'
        # headers["sec-ch-ua"] = '"Chromium";v="104", "NotA;Brand";v="99", "GoogleChrome";v="104"'
        # headers["sec-ch-ua-mobile"] = "?0"
        # headers["sec-ch-ua-platform"] = '"Linux"'
        # headers["sec-fetch-dest"] = "document"
        # headers["sec-fetch-mode"] = "navigate"
        # headers["sec-fetch-site"] = "none"
        # headers["sec-fetch-user"] = "?1"
        # headers["upgrade-insecure-requests"] = "1"
        # headers["user-agent"] = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/104.0.0.0 Safari/537.36"
        #
        # resp = requests.get(url, headers=headers, allow_redirects=True)
        #
        # print(resp.status_code)

        #####
        deals = self.hello()
        if len(deals) == 0:
            print('Error while loading deals!')
            return

        deals_res = self.get_activities(deals)

        data_contacts = '''
                     { 
                        "order": { "DATE_CREATE": "ASC" },
                        "select": [ "ID","NAME","LAST_NAME","LEAD_ID","COMPANY_ID","EMAIL","PHONE","TYPE_ID"]
                    }
                '''
        # ?filter[ENTITY_ID] = {deal["id"]} & f
        # data_contacts = "order[DATE_CREATE]=ASC&select=ID,NAME,LAST_NAME,LEAD_ID,COMPANY_ID,EMAIL,PHONE,TYPE_ID&start={s}"

        contacts = False
        if not contacts :
            contacts = self.post_from_url(f'{B24_URI}/crm.contact.list', data_contacts)


        data_company = '''
                     { 
                        "order": { "DATE_CREATE": "ASC" },
                        "select": ["ID", "TITLE", "CURRENCY_ID", "REVENUE","PHONE","EMAIL","ADDRESS"]
                    }
                '''
        # "crm.company.list",
        # {
        #     order: {"DATE_CREATE": "ASC"},
        #     filter: {"INDUSTRY": "MANUFACTURING", "COMPANY_TYPE": "CUSTOMER"},
        #     select: ["ID", "TITLE", "CURRENCY_ID", "REVENUE"]
        # },
        # companies = self.post_from_url(f'{B24_URI}/crm.company.list', data_company)
        companies = None

        env_deals = self.env['crm.lead'].env
        odoobot_id = self.env['ir.model.data'].sudo().xmlid_to_res_id("base.partner_root")
        odoobot_user_id = self.env['ir.model.data'].sudo().xmlid_to_res_id("base.user_root")

        for deal in deals_res.values():
            activity_list = deal['activities']

            external_id = deal['external_id']
            id = deal['id']
            record = env_deals.ref(external_id)

            if record:
                if activity_list:
                    dict_users = self.get_username_activities()

                    sorted_date = sorted(list(activity_list.values()),
                                         key=lambda x: (datetime.strptime(str(datetime.fromisoformat(x['CREATED']).replace(tzinfo=None)), '%Y-%m-%d %H:%M:%S')))

                    # datetime.strptime(str(datetime.fromisoformat(list(activity_list.values())[1]['CREATED']).replace(tzinfo=None)),'%Y-%m-%d %H:%M:%S')

                    # for activity in activity_list.values():
                    for activity in sorted_date:
                        date_deadline = datetime.fromisoformat(activity['DEADLINE']).replace(tzinfo=None)
                        date_deadline_str = date_deadline.strftime("%A,%d%b %Y,%H:%M")
                        create_date = datetime.fromisoformat(activity['CREATED']).replace(tzinfo=None)
                        last_update_date = datetime.fromisoformat(activity['LAST_UPDATED']).replace(tzinfo=None)
                        # message = locale_date_str + " тел:" + partner_phone + " Только что был пропущен звонок от" + partner_name + "<a href=# data-oe-model=crm.phonecall data-oe-id=%d>#%s - Ссылка на звонок</a>" % (record.id, record.name)
                        author_id = activity['AUTHOR_ID']
                        responsible_id = activity['RESPONSIBLE_ID']
                        ENTITY_TYPE_ID = int(activity['COMMUNICATIONS'][0]['ENTITY_TYPE_ID'])
                        ENTITY_ID = activity['COMMUNICATIONS'][0]['ENTITY_ID']
                        # COMPANY_TITLE = activity['COMMUNICATIONS'][0]['ENTITY_SETTINGS']['COMPANY_TITLE']
                        tel = activity['COMMUNICATIONS'][0]['VALUE']
                        # partner_company = ''

                        company_id = 0

                        # if COMPANY_TITLE:
                        #     company_search = self.env['res.partner'].search(
                        #         [('name', 'like', COMPANY_TITLE)])
                        #     if company_search:
                        #         company_id = company_search[0].id or 0


                        if len(dict_users) > 0:
                            responsible_user = next((user for user in dict_users if user['ID'] == responsible_id),
                                                    False)
                            responsible_user_lastname = responsible_user['NAME'] + ' ' +responsible_user['LAST_NAME']

                        if len(dict_users) > 0:
                            res_user = next((user for user in dict_users if user['ID']==author_id), False)
                            res_user_last_name = "<p>Автор:" + res_user['NAME'] + "&nbsp;" + res_user['LAST_NAME'] + "</p>"



                        # <a href=# data-oe-model=account.move data-oe-id={move_id}>{move_name}</a>"
                        if (ENTITY_TYPE_ID == 4):
                            COMPANY_ID = ENTITY_ID
                            # company_id = 0
                            if (len(activity['COMMUNICATIONS'][0]['ENTITY_SETTINGS']) > 0):
                                COMPANY_TITLE = activity['COMMUNICATIONS'][0]['ENTITY_SETTINGS']['COMPANY_TITLE']

                            if COMPANY_TITLE:
                                company_search = self.env['res.partner'].search(
                                    [('name', 'like', COMPANY_TITLE)])
                                if company_search:
                                    company_id = company_search[0].id or 0
                                    url_company = f'web#id={company_id}&model=res.partner'

                            # partner_company ='''
                            # <div class ="crm-timeline__card-container">
                            # <div class ="crm-timeline__card-container_block">
                            #     <div class ="crm-timeline__card-container_info --inline" >
                            #         <div class ="crm-timeline__card-container_info-title" > Крайній термін </div>
                            #             <div class ="crm-timeline__card-container_info-value">
                            #                 <span class ="crm-timeline__date-pill --color-default --readonly" >
                            #                     <span> {date_deadline_str} </span>
                            #                     <span class ="crm-timeline__date-pill_caret" > </span>
                            #                 </span>
                            #             </div>
                            #         </div>
                            # </div>
                            # <div class="crm-timeline__card-container_info --inline">
                            #     <div class="item crm-timeline__card-container_info-title">Клієнт</div>
                            #          <div class="item crm-timeline__card-container_info-value">
                            #             <a href=# data-oe-model=res.partner data-oe-id={company_id}  class="crm-timeline__card_link --bold">
                            #                 {COMPANY_TITLE}&nbsp;{tel}</a>
                            #         </div>
                            #     </div>
                            # <div class="crm-timeline__card-container_info --inline">
                            #     <div class="crm-timeline__card-container_info-title">
                            #         Відповідальна особа
                            #     </div>
                            #     <div class="crm-timeline__card-container_info-value">
                            #         <a href="/" class="crm-timeline__card_link --bold">
                            #          {responsible_user_lastname}</a>
                            #     </div>
                            # </div>
                            # </div>
                            # '''.format(date_deadline_str=date_deadline_str, COMPANY_TITLE=COMPANY_TITLE,tel=tel,responsible_user_lastname=responsible_user_lastname,
                            #            company_id=company_id)
                            date_deadline_fmt = self.date_deadline_tml.format(date_deadline_str=date_deadline_str)
                            company_fmt = self.company_tml.format(COMPANY_TITLE=COMPANY_TITLE,tel=tel,company_id=company_id)
                            responsible_user_fmt = self.responsible_user_tml.format(responsible_user_lastname=responsible_user_lastname)
                            partner_company_fmt = self.partner_company.format(date_deadline_tml=date_deadline_fmt,
                                                        communication_name_tml='',
                                                        company_tml=company_fmt,
                                                        responsible_user_tml=responsible_user_fmt)


                        elif(ENTITY_TYPE_ID == 3):
                            partner_id = 0

                            if len(contacts) > 0:
                                contact = next((contact for contact in contacts if contact['ID'] == ENTITY_ID), False)
                                contact_name = "<p>Автор:" + contact['NAME'] + "&nbsp;" + contact['LAST_NAME'] + "</p>"

                            if contact:
                                partner_search = self.env['res.partner'].search([('name', 'like', contact['LAST_NAME']),('name', 'like', contact['NAME'])])
                                if partner_search:
                                    partner_id = partner_search[0].id or 0
                                    url_partner = f'web#id={partner_id}&model=res.partner'


                            if(len(activity['COMMUNICATIONS'][0]['ENTITY_SETTINGS'])>0):
                                COMMUNICATIONS_NAME = activity['COMMUNICATIONS'][0]['ENTITY_SETTINGS']['NAME'] + ' ' + activity['COMMUNICATIONS'][0]['ENTITY_SETTINGS']['LAST_NAME']

                                COMMUNICATIONS_LAST_NAME = activity['COMMUNICATIONS'][0]['ENTITY_SETTINGS']['LAST_NAME']
                                COMPANY_TITLE = activity['COMMUNICATIONS'][0]['ENTITY_SETTINGS']['COMPANY_TITLE']
                                COMPANY_ID = activity['COMMUNICATIONS'][0]['ENTITY_SETTINGS']['COMPANY_ID']

                                if COMPANY_TITLE:
                                    company_search = self.env['res.partner'].search(
                                        [('name', 'like', COMPANY_TITLE)])
                                    if company_search:
                                        company_id = company_search[0].id or 0
                                        url_company = f'web#id={company_id}&model=res.partner'

                                # partner_company = '''
                                #                 <div class ="crm-timeline__card-container">
                                #                 <div class ="crm-timeline__card-container_block">
                                #                     <div class ="crm-timeline__card-container_info --inline" >
                                #                         <div class ="crm-timeline__card-container_info-title" > Крайній термін </div>
                                #                             <div class ="crm-timeline__card-container_info-value">
                                #                                 <span class ="crm-timeline__date-pill --color-default --readonly" >
                                #                                     <span> {date_deadline_str} </span>
                                #                                     <span class ="crm-timeline__date-pill_caret" > </span>
                                #                                 </span>
                                #                             </div>
                                #                         </div>
                                #                 </div>
                                #                 <div class="crm-timeline__card-container_info --inline">
                                #                     <div class="item crm-timeline__card-container_info-title">Клієнт</div>
                                #                          <div class="item crm-timeline__card-container_info-value">
                                #                             <a href=# data-oe-model=res.partner data-oe-id={partner_id}  class="crm-timeline__card_link --bold">
                                #                                 {COMMUNICATIONS_NAME}&nbsp;{tel}</a>
                                #                     </div>
                                #                 </div>
                                #                 <div class="crm-timeline__card-container_info --inline">
                                #                     <div class="item crm-timeline__card-container_info-title">Компанія</div>
                                #                          <div class="item crm-timeline__card-container_info-value">
                                #                             <a href="# data-oe-model=res.partner data-oe-id={company_id}" class="crm-timeline__card_link --bold">
                                #                                 {COMPANY_TITLE}</a>
                                #                     </div>
                                #                 </div>
                                #                 <div class="crm-timeline__card-container_info --inline">
                                #                     <div class="crm-timeline__card-container_info-title">
                                #                         Відповідальна особа
                                #                     </div>
                                #                     <div class="crm-timeline__card-container_info-value">
                                #                         <a href="/" class="crm-timeline__card_link --bold">
                                #                          {responsible_user_lastname}</a>
                                #                     </div>
                                #                 </div>
                                #                 </div>
                                #                 '''.format(date_deadline_str=date_deadline_str,COMMUNICATIONS_NAME=COMMUNICATIONS_NAME,tel=tel,
                                #                             COMPANY_TITLE=COMPANY_TITLE, responsible_user_lastname=responsible_user_lastname,
                                #                             partner_id=partner_id, company_id=company_id)

                                date_deadline_fmt = self.date_deadline_tml.format(date_deadline_str=date_deadline_str)
                                communication_name_fmt = self.communication_name_tml.format(COMMUNICATIONS_NAME=COMMUNICATIONS_NAME,partner_id=partner_id, tel=tel)
                                company_fmt = self.company_tml.format(COMPANY_TITLE=COMPANY_TITLE, tel=tel,
                                                                      company_id=company_id)
                                responsible_user_fmt = self.responsible_user_tml.format(
                                    responsible_user_lastname=responsible_user_lastname)
                                partner_company_fmt = self.partner_company.format(date_deadline_tml=date_deadline_fmt,
                                                                                  communication_name_tml=communication_name_fmt,
                                                                                  company_tml=company_fmt,
                                                                                  responsible_user_tml=responsible_user_fmt)

                            else:
                                # partner_company = '<div>' + \
                                #                   '<div><span>Крайний срок:</span><span class="date_deadline">' + date_deadline_str + '</span></div>' + \
                                #                   '<div><span>Ответственный:</span>' + '<span>' + responsible_user_lastname + '</span></div>' + \
                                #                   '</div>'
                                # partner_company = '''
                                #                     <div class ="crm-timeline__card-container">
                                #                     <div class ="crm-timeline__card-container_block">
                                #                         <div class ="crm-timeline__card-container_info --inline" >
                                #                             <div class ="crm-timeline__card-container_info-title" > Крайній термін </div>
                                #                                 <div class ="crm-timeline__card-container_info-value">
                                #                                     <span class ="crm-timeline__date-pill --color-default --readonly" >
                                #                                         <span> {date_deadline_str} </span>
                                #                                         <span class ="crm-timeline__date-pill_caret" > </span>
                                #                                     </span>
                                #                                 </div>
                                #                             </div>
                                #                     </div>
                                #                     <div class="crm-timeline__card-container_info --inline">
                                #                         <div class="crm-timeline__card-container_info-title">
                                #                             Відповідальна особа
                                #                         </div>
                                #                         <div class="crm-timeline__card-container_info-value">
                                #                             <a href="/" class="crm-timeline__card_link --bold">
                                #                              {responsible_user_lastname}</a>
                                #                         </div>
                                #                     </div>
                                #                     </div>
                                #                     '''.format(date_deadline_str=date_deadline_str,responsible_user_lastname=responsible_user_lastname)
                                date_deadline_fmt = self.date_deadline_tml.format(date_deadline_str=date_deadline_str)
                                responsible_user_fmt = self.responsible_user_tml.format(
                                    responsible_user_lastname=responsible_user_lastname)
                                partner_company_fmt = self.partner_company.format(date_deadline_tml=date_deadline_fmt,
                                                                                  communication_name_tml='',
                                                                                  company_tml='',
                                                                                  responsible_user_tml=responsible_user_fmt)

                        else:
                            if len(activity['COMMUNICATIONS']) > 1:
                                if(len(activity['COMMUNICATIONS'][1]['ENTITY_SETTINGS']) > 0):

                                    COMMUNICATIONS_NAME = activity['COMMUNICATIONS'][1]['ENTITY_SETTINGS']['NAME'] + ' ' + \
                                                          activity['COMMUNICATIONS'][1]['ENTITY_SETTINGS']['LAST_NAME']

                                    COMMUNICATIONS_LAST_NAME = activity['COMMUNICATIONS'][1]['ENTITY_SETTINGS']['LAST_NAME']
                                    COMPANY_TITLE = activity['COMMUNICATIONS'][1]['ENTITY_SETTINGS']['COMPANY_TITLE']
                                    COMPANY_ID = activity['COMMUNICATIONS'][1]['ENTITY_SETTINGS']['COMPANY_ID']
                                    ENTITY_TYPE_ID = int(activity['COMMUNICATIONS'][1]['ENTITY_TYPE_ID'])
                                    ENTITY_ID = activity['COMMUNICATIONS'][1]['ENTITY_ID']
                                    COMPANY_TITLE = activity['COMMUNICATIONS'][1]['ENTITY_SETTINGS']['COMPANY_TITLE']
                                    tel = activity['COMMUNICATIONS'][1]['VALUE']
                                    partner_company = ''
                                    company_id = 0

                                    if COMPANY_TITLE:
                                        company_search = self.env['res.partner'].search(
                                            [('name', 'like', COMPANY_TITLE)])
                                        if company_search:
                                            company_id = company_search[0].id or 0



                                # elif (ENTITY_TYPE_ID == 3):
                                partner_id = 0

                                if len(contacts) > 0:
                                    contact = next((contact for contact in contacts if contact['ID'] == ENTITY_ID), False)
                                    contact_name = "<p>Автор:" + contact['NAME'] + "&nbsp;" + contact['LAST_NAME'] + "</p>"

                                if contact:
                                    partner_search = self.env['res.partner'].search(
                                        [('name', 'like', contact['LAST_NAME']), ('name', 'like', contact['NAME'])])
                                    if partner_search:
                                        partner_id = partner_search[0].id or 0
                                        url_partner = f'web#id={partner_id}&model=res.partner'
                                    # partner_company =   '<div>' + \
                                #                     '<div><span>Крайний срок:</span><span class="date_deadline">' + date_deadline_str + '</span></div>' + \
                                #                     '<div><span>Ответственный:</span>' + '<span>' + responsible_user_lastname + '</span></div>' + \
                                #                      '</div>'
                                # partner_company = '''
                                #                         <div class ="crm-timeline__card-container">
                                #                         <div class ="crm-timeline__card-container_block">
                                #                             <div class ="crm-timeline__card-container_info --inline" >
                                #                                 <div class ="crm-timeline__card-container_info-title" > Крайній термін </div>
                                #                                     <div class ="crm-timeline__card-container_info-value">
                                #                                         <span class ="crm-timeline__date-pill --color-default --readonly" >
                                #                                             <span> {date_deadline_str} </span>
                                #                                             <span class ="crm-timeline__date-pill_caret" > </span>
                                #                                         </span>
                                #                                     </div>
                                #                                 </div>
                                #                         </div>
                                #                         <div class="crm-timeline__card-container_info --inline">
                                #                             <div class="crm-timeline__card-container_info-title">
                                #                                 Відповідальна особа
                                #                             </div>
                                #                             <div class="crm-timeline__card-container_info-value">
                                #                                 <a href="/" class="crm-timeline__card_link --bold">
                                #                                  {responsible_user_lastname}</a>
                                #                             </div>
                                #                         </div>
                                #                         </div>
                                #                         '''.format(date_deadline_str=date_deadline_str,
                                #                                     responsible_user_lastname=responsible_user_lastname)
                                date_deadline_fmt = self.date_deadline_tml.format(date_deadline_str=date_deadline_str)
                                communication_name_fmt = self.communication_name_tml.format(
                                    COMMUNICATIONS_NAME=COMMUNICATIONS_NAME, partner_id=partner_id, tel=tel)
                                company_fmt = self.company_tml.format(COMPANY_TITLE=COMPANY_TITLE, tel=tel,
                                                                      company_id=company_id)
                                responsible_user_fmt = self.responsible_user_tml.format(
                                    responsible_user_lastname=responsible_user_lastname)
                                partner_company_fmt = self.partner_company.format(date_deadline_tml=date_deadline_fmt,
                                                                                  communication_name_tml=communication_name_fmt,
                                                                                  company_tml=company_fmt,
                                                                                  responsible_user_tml=responsible_user_fmt)

                        if res_user:
                            user_search  = self.env['res.users'].search([('name', 'like', res_user['LAST_NAME'])])
                            if user_search:
                                user_id = user_search[0].partner_id.id
                                su_id = user_search[0].id
                                res_user_last_name = ''
                            else:
                                # user_id = self.env.uid
                                user_id = odoobot_id
                                su_id = odoobot_user_id


                        if activity['START_TIME']:
                            start_time_date = datetime.fromisoformat(activity['START_TIME']).replace(tzinfo=None)

                        deal_create_date = datetime.fromisoformat(str(record.create_date)).replace(tzinfo=None)

                        create_date = create_date or last_update_date or start_time_date or deal_create_date

                        # date_deadline = fields.Datetime.now()+timedelta(days=1)
                        date_today = fields.Date.context_today(self)

                        note = activity['SUBJECT'] +res_user_last_name+ partner_company_fmt
                        summary = activity['SUBJECT']
                        if (activity['PROVIDER_TYPE_ID'] == "CALL"):
                            summary = re.sub('(на.+(\d+\s\d+))|(на.+\d+)|(від.+(\d+\s\d+))', ' дзвінок', activity['SUBJECT'])
                            note = re.sub('(Вихідний на.+(\d+\s\d+))|(на.+\d+)|(Вхідний від.+(\d+\s\d+))','',note)
                        elif(activity['PROVIDER_TYPE_ID'] =="2"):
                            note = ' '

                        if (activity['PROVIDER_TYPE_ID'] == "CALL"):
                            activity_typ = 'mail.mail_activity_data_call'
                        elif (activity['PROVIDER_TYPE_ID'] == "EMAIL"):
                            activity_typ = 'mail.mail_activity_data_email'
                        elif (activity['PROVIDER_TYPE_ID'] == "TASK"):
                            activity_typ = 'mail.mail_activity_data_todo'
                        else:
                            activity_typ = None

                        #   https://asoft.bitrix24.ua/bitrix/tools/crm_show_file.php?fileId=244574&ownerTypeId=6&ownerId=175130&auth=
                        #   https://asoft.bitrix24.ua/rest/178/in25s0uxw7tr0dnh/
                        #   https://asoft.bitrix24.ua/rest/178/in25s0uxw7tr0dnh/bitrix/tools/crm_show_file.php?fileId=244574&ownerTypeId=6&ownerId=175130&auth=
                        phone_file_attachments = []
                        attachment = []
                        if ('FILES' in activity.keys()):
                            for phone_file in activity['FILES']:
                                #
                                file_id = {'id': phone_file['id']}
                                req_file = requests.post(f'{B24_URI}/disk.file.get', json=file_id)
                                if req_file.status_code != 200:
                                    print('Error accessing to file B24!')
                                    continue

                                resp_file_json = req_file.json()
                                res_file = resp_file_json['result']

                                if len(res_file) > 0:
                                    download_url = res_file['DOWNLOAD_URL']
                                    download_url = download_url.replace('\\','')
                                #
                                phone_f_name = str(phone_file['id'])+'.mp3'
                                headers = {'Content-Type': 'audio/mpeg'}
                                # req = requests.get(phone_file['url'], headers = headers)
                                req = requests.get(download_url, headers = headers)
                                req_out = base64.b64encode(req.content).decode('utf-8')
                                phone_file_attachments.append((phone_f_name, req.content))
                                #
                                # with open('/opt/odoo14/pjts/learn/repo/biko_load_comments/audio1.mp3','w+b') as f:
                                #     f.write(req.content)
                                #     f.close()

                                attachment_obj = self.env['ir.attachment'].create({
                                    'name': phone_f_name,
                                    'datas': req_out,
                                    'type': 'binary',
                                    'mimetype': 'audio/mpeg',
                                })
                                attachment.append(attachment_obj.id)
                        # print(record)
                        # print(activity_typ)
                        # print(su_id)
                        # print(date_deadline)
                        act_env = record.activity_schedule(activity_typ, user_id=su_id, date_deadline=date_deadline,
                                                           summary=summary, note=note)
                        act_env['create_date'] = create_date
                        act_env['create_uid'] = responsible_id

                        # act_env.write({'write_date': create_date})
                        # act_env.write({'date_deadline': date_today})

                        # res = act_env.env.cr.execute(
                        #     """SELECT * FROM mail_activity;""")
                        # fresult = act_env.env.cr.fetchall()
                        # act_env.env.cr.execute(
                        #     """UPDATE mail_activity SET create_date='2020-01-01 00:00:00',write_date='2020-01-01 00:00:00' WHERE id=%d;""" % act_env.id)
                        # act_env.env.cr.execute(
                        # """SELECT * FROM information_schema.columns WHERE table_name = 'mail_activity' """)
                        act_env_id = act_env.res_id
                        act_note = act_env.note

                        if activity['COMPLETED'] == 'Y':
                            message_id = act_env.action_feedback(feedback=' ')
                            act_to_message = self.env['mail.message'].browse([message_id])
                            act_to_message.write({'date': create_date, 'author_id': user_id, 'attachment_ids':attachment})


                        # curr_act = self.env['mail.message'].search([('res_id', '=', act_env_id),('body','like',act_note)])
                        # curr_act[0].write({'date': create_date})
                        # curr_act = self.env['mail.message'].search([('res_id','=',act_env.id)])
                        # curr_act.env.cr.execute(
                        #     """UPDATE mail_activity SET create_date='2020-01-01 00:00:00',write_date='2020-01-01 00:00:00';""")
                        # curr_act.env.cr.commit()
                        #
                        # act_env.env.cr.commit()
                        #
                        # curr_act = self.env['mail.activity'].browse([act_env.id])
                        # curr_act.env.cr.execute("""UPDATE mail_activity SET create_date='2020-01-01 00:00:00',write_date='2020-01-01 00:00:00';""")
                        # curr_act.env.cr.commit()
                        #
                        # res = act_env.env.cr.execute(
                        #     """SELECT * FROM mail_activity;""")
                        # fresult = act_env.env.cr.fetchall()
                        # fresult.env.cr.commit()
        return 1


    def action_import_activities_comments(self):
        bitrix_hook_url = self.env['ir.config_parameter'].sudo().get_param('biko_load_comments.bitr_url')
        if not bitrix_hook_url:
            raise UserError(_("Module requires parameter in Settings '%s' ", 'Bitrix Webhook Url'))
        B24_URI = bitrix_hook_url

        self.action_import_records()
        print('import_records--------------:)')
        self.action_import_activities()
        print('import_activities============:)')


# class ResConfigSettings(models.TransientModel):
#     _inherit = 'res.config.settings'
#
#     bitrix_url = fields.Char(string="Bitrix Webhook Url", config_parameter='biko_load_comments.bitrix_url')
#     # allow_planned_activity = fields.Boolean(string="Allow Import Planned Activity")
#
#     @api.model
#     def get_values(self):
#         res = super(ResConfigSettings, self).get_values()
#         bitrix_url = self.env["ir.config_parameter"].get_param(
#             "biko_load_comments.config.bitrix_url")
#         # allow_planned_activity = self.env['ir.config_parameter'].sudo().get_param(
#         #     'biko_load_comments.config.allow_planned_activity')
#         res.update({
#             'bitrix_url': bitrix_url if type(bitrix_url) else False
#             # 'allow_planned_activity': allow_planned_activity
#             }
#         )
#         return res
#
#     # @api.model
#     # def set_values(self):
#     #     # self.env['ir.config_parameter'].sudo().set_param(
#     #     #     'biko_load_comments.config.bitrix_url', self.bitrix_url)
#     #     # self.env['ir.config_parameter'].sudo().set_param(
#     #     #     'biko_load_comments.config.allow_planned_activity', self.allow_planned_activity)
#     #     super(ResConfigSettings, self).set_values()
#     #     # return res


