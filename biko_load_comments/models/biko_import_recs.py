from odoo import models, fields
import base64
import json
from datetime import datetime
import requests
from requests.structures import CaseInsensitiveDict
from datetime import timedelta
import csv
import yaml
import os

B24_URI = ''
# RESULT_FILE = ''
# SOURCE_FILE = ''
# CHARSET = ''

relpath = os.path.dirname(os.path.realpath(__file__))

with open(relpath + '/settings.yaml', 'r', encoding='UTF_8') as yaml_file:
    objects = yaml.load(yaml_file, yaml.Loader)
    B24_URI = objects['B24_WEBHOOK'] if objects['B24_WEBHOOK'][-1] != '/' else objects['B24_WEBHOOK'][0:-1]
    # RESULT_FILE = objects['RESULT_FILE']
    # SOURCE_FILE = objects['SOURCE_FILE']
    # CHARSET = objects['CHARSET']

headers = CaseInsensitiveDict()
headers["Content-Type"] = "application/json"


def common():
    print('common')

class ImportRecs(models.TransientModel):
    _name = 'biko.import.recs'

    file = fields.Binary(string='File name')
    file_name = fields.Char()
    charset = fields.Selection(selection=[('UTF-8', 'UTF-8'), ('windows-1251', 'windows-1251')], string='Charset')

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
                                    deal['comments'][comment_line['ID']]['FILES'][file]['urlDownload'] = res_file['DOWNLOAD_URL'];

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

            data_id = f'{{"filter": {{"OWNER_TYPE_ID": 2,"OWNER_ID": {deal["id"]} }}  ,"select":[ "*", "COMMUNICATIONS" ] }}'
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

    def action_import_records(self):
        # deals = self.get_deals()
        deals = self.hello()
        if len(deals) == 0:
            print('Error while loading deals!')
            return

        deals_res, deals_with_files = self.get_comments(deals)
        deals_res = self.get_activities(deals_res)

        env_deals = self.env['crm.lead'].env

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
        deals = self.hello()
        if len(deals) == 0:
            print('Error while loading deals!')
            return


        deals_res = self.get_activities(deals)

        env_deals = self.env['crm.lead'].env

        for deal in deals_res.values():
            activity_list = deal['activities']

            external_id = deal['external_id']
            id = deal['id']
            record = env_deals.ref(external_id)

            if record:
                if activity_list:
                    dict_users = self.get_username_activities()
                    for activity in activity_list.values():
                        author_id = activity['AUTHOR_ID']


                        if len(dict_users) > 0:
                            res_user = next((user for user in dict_users if user['ID']==author_id), False)


                        if res_user:
                            user_search  = self.env['res.users'].search([('name', 'like', res_user['LAST_NAME'])])
                            if user_search:
                                user_id = user_search.id
                            else:
                                user_id = self.env.uid

                        date_deadline = datetime.fromisoformat(activity['DEADLINE']).replace(tzinfo=None)
                        # date_deadline = fields.Datetime.now()+timedelta(days=1)
                        # date_deadline = fields.Date.context_today(self)
                        note = activity['SUBJECT']

                        if (activity['PROVIDER_TYPE_ID'] == "CALL"):
                            activity_typ = 'mail.mail_activity_data_call'
                        else:
                            activity_typ = None

                        act_env = record.activity_schedule(activity_typ, user_id=user_id, date_deadline=date_deadline,
                                                           summary=note, note=note)
                        if activity['COMPLETED'] == 'Y':
                            act_env.action_feedback(feedback='ok')
