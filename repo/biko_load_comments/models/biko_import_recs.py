from odoo import models, fields, api,modules,sql_db, _
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
from odoo import tools
from odoo.exceptions import UserError
# from . import load_comments_mail_tml
import urllib.parse
import logging
from odoo.api import Environment, SUPERUSER_ID
from fast_bitrix24 import Bitrix
# from fast_bitrix24 import BitrixAsync
# from .biko_load_res_config_settings import ResConfigSettings
# from contextlib import closing
# import odoo

# pip install fast-bitrix24

# with api.Environment.manage():
#     # registry = modules.registry.RegistryManager.get(tools.config['db_name'])
#     registry = modules.registry.Registry(tools.config['db_name'])
#     with registry.cursor() as cr:
#         # Load our context and environment given the database cursor and UID
#         # ctx = api.Environment(cr, SUPERUSER_ID, {})['res.users'].context_get()
#         ctx = api.Environment(cr, SUPERUSER_ID, {})['res.users']
#         env = api.Environment(cr, SUPERUSER_ID, ctx)
        # config = env['ir.config_parameter'].get_param('biko_load_comments.bitr_url', 'url')

hk_logger = logging.getLogger(__name__)
# def get_config_bitrix(param):
#     try:
#         db = sql_db.db_connect(tools.config['db_name'])  # You can get the db name from config
#         cr = db.cursor()
#         # cr.execute("select * from ir_config_parameter where key='biko_load_comments.bitr_url'")
#         cr.execute(f"select * from ir_config_parameter where key='{param}'")
#         data = cr.dictfetchall()[0]['value']
#         cr.commit()
#         cr.close()
#     except Exception as e:
#         cr.rollback()
#         cr.close()
#         hk_logger.error("getting config parameter error encountered: {}".format(e), exc_info=True)
#     return data

B24_URI = ''
# B24_URI = get_config_bitrix('biko_load_comments.bitr_url')
# b = False
# b = Bitrix(B24_URI)
# RESULT_FILE = ''
# SOURCE_FILE = ''
# CHARSET = ''
contacts = False
dict_users = False
relpath = os.path.dirname(os.path.realpath(__file__))


with open(relpath + '/settings.yaml', 'r', encoding='UTF_8') as yaml_file:
    objects = yaml.load(yaml_file, yaml.Loader)
    B24_URI = objects['B24_WEBHOOK'] if objects['B24_WEBHOOK'][-1] != '/' else objects['B24_WEBHOOK'][0:-1]
    # RESULT_FILE = objects['RESULT_FILE']
    # SOURCE_FILE = objects['SOURCE_FILE']
    # CHARSET = objects['CHARSET']

b = False
b = Bitrix(B24_URI)

headers = CaseInsensitiveDict()
headers["Content-Type"] = "application/json"



class ImportComments(models.Model):
    _inherit = 'crm.lead'


    def __init__(self,pool, cr):
        pass
        # bitrix_hook_url = self.env['ir.config_parameter'].sudo().get_param('biko_load_comments.bitr_url')
        # if not bitrix_hook_url:
        #     raise UserError(_("Module requires parameter in Settings '%s' ", 'Bitrix Webhook Url'))
        # global B24_URI
        # B24_URI = bitrix_hook_url
        # global b
        # b = Bitrix(B24_URI)
        # init_res = super(self).__init__(pool, cr)
        # return init_res


    partner_company_tml = '''
                    <div class ="crm-timeline__card-container">
                        <div class ="crm-timeline__card-container_block">
                            {date_deadline_tml}
                            {communication_name_tml}
                            {company_tml}
                            {responsible_user_tml}
                        </div>
                    </div>
                    '''

    date_deadline_tml = '''
            <div class ="crm-timeline__card-container_info --inline" >
                <div class ="crm-timeline__card-container_info-title" > Крайній термін </div>
                    <div class ="crm-timeline__card-container_info-value"> 
                        <span class ="crm-timeline__date-pill --color-default --readonly" > 
                            <span> {date_deadline_str} </span>
                            <span class ="crm-timeline__date-pill_caret" > </span> 
                        </span> 
                    </div>
                </div>
            </div>
        '''

    communication_name_tml = '''
                <div class="crm-timeline__card-container_info --inline">
                        <div class="item crm-timeline__card-container_info-title">Клієнт</div>
                            <div class="item crm-timeline__card-container_info-value">
                                <a href=# data-oe-model=res.partner data-oe-id={partner_id}  class="crm-timeline__card_link --bold">
                                {COMMUNICATIONS_NAME}&nbsp;{tel}</a>
                        </div>
                </div>
        '''

    company_tml = '''
            <div class="crm-timeline__card-container_info --inline">
                            <div class="item crm-timeline__card-container_info-title">Компанія</div>
                                <div class="item crm-timeline__card-container_info-value">
                                    <a href=# data-oe-model=res.partner data-oe-id={company_id} class="crm-timeline__card_link --bold">
                                        {COMPANY_TITLE}&nbsp;{tel}</a>
                            </div>
            </div>
        '''

    responsible_user_tml = '''
            <div class="crm-timeline__card-container_info --inline">
                    <div class="crm-timeline__card-container_info-title">
                        Відповідальна особа
                    </div>
                    <div class="crm-timeline__card-container_info-value">
                        <a href=# data-oe-model=res.users data-oe-id=1 class="crm-timeline__card_link --bold">
                         {responsible_user_lastname}</a>
                    </div>
            </div>
        '''

    # contacts = None

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
        # bitrix_hook_url = self.env['ir.config_parameter'].sudo().get_param('biko_load_comments.bitr_url')
        # if not bitrix_hook_url:
        #     raise UserError(_("Module requires parameter in Settings '%s' ", 'Bitrix Webhook Url'))
        # global B24_URI
        # B24_URI = bitrix_hook_url
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
        # global  B24_URI
        # global b
        #
        # activities_3 = b.get_all('crm.activity.list',params={'select': ['*', 'COMMUNICATIONS'],'filter': {'OWNER_TYPE_ID': 3, 'OWNER_ID': 7495}})
        # activities_2 = b.get_all(
        #     'crm.activity.list',
        #     params={
        #         'select': ['*', 'COMMUNICATIONS'],
        #         'filter': {'OWNER_TYPE_ID': 2, 'OWNER_ID': 5449}
        #     })
        # activities_3 = activities_3 + activities_2
        # activities_sorted = sorted(activities_3, key=lambda i: i['ID'])
        # json_activities = json.dumps(activities_sorted, ensure_ascii=False)

        #     https://asoft.bitrix24.ua/rest/178/i/crm.contact.list?order[DATE_CREATE]=ASC&select=ID&select=NAME&select=LAST_NAME&select=LEAD_ID&select=COMPANY_ID&select=EMAIL&select=PHONE&select=TYPE_ID&start=50
        #     https://asoft.bitrix24.ua/rest/178/i/crm.activity.list?order[DATE_CREATE]=ASC&select=ID&select=NAME&select=LAST_NAME&select=LEAD_ID&select=COMPANY_ID&select=EMAIL&select=PHONE&select=TYPE_ID&start=50
        deals_with_files = {}


        templ_start = '{"halt":0,"cmd": {'
        templ_end = '}}'
        i = 0
        packages = []
        req_str = ""

        #
        # data_id = f'{{"order": {{"ID": "DESC"}},"filter": {{"OWNER_ID": 7717}}  ,"select":[ "*", "COMMUNICATIONS" ] }}'
        # json_res = json.dumps(json.loads(data_id))
        # req = requests.post(f'{B24_URI}/crm.activity.list', headers=headers, data=json_res)
        # # req = requests.post(f'{B24_URI}crm.activity.list', data=json_res)
        #
        # if req.status_code != 200:
        #     print('Error accessing to B24!')
        #
        #
        # resp_json = req.json()
        # res_activity = resp_json['result']
        #
        for deal in deals.values():
            req_str += f'"{deal["id"]}":"crm.activity.list?order[CREATED]=DESC&filter[OWNER_ID]={deal["id"]}&filter[OWNER_TYPE_ID]=2&select=*&select=COMMUNICATIONS",'
            # req_str += '"7717":"crm.activity.list?order[CREATED]=DESC&filter[OWNER_ID]=7717&filter[OWNER_TYPE_ID]=2&select=*&select=COMMUNICATIONS",'
            # req_str += '"7717":"crm.activity.list?filter[OWNER_ID]=7717&select=ID&select=SUBJECT&select=DESCRIPTION",'
            # '{"halt":0,"cmd": {'
            # templ_end = '}}'
            # curl  -s 'https://asoft.bitrix24.ua/rest/178/in25sh/batch'\
            # -H "Content-Type: application/json;charset=utf-8" -d '{"halt":0,"cmd": {"7717":"crm.activity.list?order[CREATED]=DESC&filter[OWNER_ID]=7717&filter[OWNER_TYPE_ID]=2&select=*&select=COMMUNICATIONS"}}' | json_pp -o '/home/alexandr/response1.txt'
            # curl - s 'https://asoft.bitrix24.ua/rest/178/i/batch' \
            # - H "Content-Type: application/json;charset=utf-8" - d '{"halt":0,"cmd": {"7717":"crm.activity.list?order[CREATED]=DESC&filter[OWNER_ID]=7717&filter[OWNER_TYPE_ID]=2&select=*&select=COMMUNICATIONS"}}' | json_pp - o '/home/alexandr/response1.txt'
            # curl - s
            # 'https://asoft.bitrix24.ua/rest/178/i/batch' - H
            # "Content-Type: application/json;charset=utf-8" - d
            # '{"halt":0,"cmd": {"7717":"crm.activity.list?order[CREATED]=DESC&filter[OWNER_ID]=7717&filter[OWNER_TYPE_ID]=2&select=*&select=COMMUNICATIONS"}}' | json_pp
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



            # param_str = json.dumps(req,ensure_ascii=False)
            resp_json = req.json()
            res_errors = resp_json['result']['result_error']
            res = resp_json['result']['result']

            if len(res_errors) > 0:
                for key, val in res_errors.items():
                    print(key, ':', val['error_description'])

            if len(res) > 0:
                for deal_id, activity in res.items():
                    deal = deals[deal_id]
                    for activity_line in activity:
                        deal['activities'].update({activity_line['ID']: activity_line})

            #
            # for deal in deals.values():
            #     # COMPLETED
            #     allow_planned_activity = bool(self.env['ir.config_parameter'].sudo().get_param('biko_load_comments.allow_activity'))
            #     if allow_planned_activity:
            #         data_id = f'{{"filter": {{"OWNER_TYPE_ID": 2,"OWNER_ID": {deal["id"]} }}  ,"select":[ "*", "COMMUNICATIONS" ] }}'
            #     else:
            #         data_id = f'{{"filter": {{"OWNER_TYPE_ID": 2,"OWNER_ID": {deal["id"]},"COMPLETED":"YES" }}  ,"select":[ "*", "COMMUNICATIONS" ] }}'


            # {
            #         order:{ "ID": "DESC" },
            #         filter:
            #         {
            #             "OWNER_TYPE_ID": 3,
            #             "OWNER_ID": 102
            #         },
            #         select:[ "*", "COMMUNICATIONS" ]
            # data_id = f'{{"order": {{"ID": "DESC"}},"filter": {{"OWNER_TYPE_ID": 2,"OWNER_ID": 7717}}  ,"select":[ "*", "COMMUNICATIONS" ] }}'
            # json_res = json.dumps(json.loads(data_id))
            # req = requests.post(f'{B24_URI}/crm.activity.list', headers=headers, data=json_res)
            # # req = requests.post(f'{B24_URI}crm.activity.list', data=json_res)
            #
            # if req.status_code != 200:
            #     print('Error accessing to B24!')
            #     # continue
            #
            # resp_json = req.json()
            # res_activity = resp_json['result']

            # if len(res_activity) > 0:
            #     for activity in res_activity:
            #         deal = deals[activity['OWNER_ID']]
            #         deal['activities'].update({activity['ID']: activity})

        return deals

    def get_activities_bitrix(self, deals):
        global B24_URI
        global b

        for deal in deals.values():
            # COMPLETED
            allow_planned_activity = bool(self.env['ir.config_parameter'].sudo().get_param('biko_load_comments.allow_activity'))
            param_http_activity = not allow_planned_activity and '&filter[COMPLETED]=YES' or ''

            results_batch = b.call_batch({
                'halt': 0,
                'cmd': {
                    'contacts': f'crm.deal.contact.items.get?id={deal["id"]}',
                    'activities_2': f'crm.activity.list?filter[OWNER_ID]={deal["id"]}&filter[OWNER_TYPE_ID]=2{param_http_activity}&select[]=*&select[]=COMMUNICATIONS',
                    'activities_3': f'crm.activity.list?filter[OWNER_ID]=$result[contacts][0][CONTACT_ID]&filter[OWNER_TYPE_ID]=3{param_http_activity}&select[]=*&select[]=COMMUNICATIONS'
                }
            })
            #
            # b.call_batch({
            #     'halt': 0,
            #     'cmd': {
            #         'activities_2': f'crm.activity.list?order[CREATED]=DESC&filter[OWNER_ID]=5449&filter[OWNER_TYPE_ID]=2&select[]=OWNER_TYPE_ID&select[]=COMMUNICATIONS'
            #     }
            # })
            # activities_2 = b.get_all(
            #     'crm.activity.list',
            #     params={
            #         'select': ['*', 'COMMUNICATIONS'],
            #         'filter': {'OWNER_TYPE_ID': 2, 'OWNER_ID': f'{deal["id"]}'}
            #     })
            #
            if len(results_batch['activities_2']) > 0:
                res_activities = results_batch['activities_2'] + results_batch['activities_3']
                deal['activities'].update({activ['ID']: activ for activ in res_activities})

        return deals


    def  get_all_bitrix(self, method, params):
        global b
        entity_list = b.get_all(method, params=params)
        return entity_list

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
        # https://asoft.bitrix24.ua/rest/178/i/crm.contact.list?order[DATE_CREATE]=ASC&select=ID&select=NAME&select=LAST_NAME&select=LEAD_ID&select=COMPANY_ID&select=EMAIL&select=PHONE&select=TYPE_ID&start=50
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



    def action_import_records(self):
        # deals = self.get_deals()
        deals = self.hello()
        if len(deals) == 0:
            print('Error while loading deals!')
            return

        deals_res, deals_with_files = self.get_comments(deals)
        # deals_res = self.get_activities(deals_res)

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



    def action_import_activities(self):
        deals = self.hello()
        if len(deals) == 0:
            print('Error while loading deals!')
            return

        deals_res = self.get_activities_bitrix(deals)

        data_contacts = {
            # "order": { "DATE_CREATE": "ASC" },
            "select": ["ID", "NAME", "LAST_NAME", "LEAD_ID", "COMPANY_ID", "EMAIL", "PHONE", "TYPE_ID"]
        }
        global contacts
        global dict_users

        if not contacts:
            contacts = self.get_all_bitrix('crm.contact.list', data_contacts)
            # contacts = self.post_from_url(f'{B24_URI}/crm.contact.list', data_contacts)

        #test activity
        # data_id = f'{{"order": {{"ID": "DESC"}},"filter": {{"OWNER_ID": 7717}}  ,"select":[ "*", "COMMUNICATIONS" ] }}'
        # req_str += f'"{deal["id"]}":"crm.activity.list?order[CREATED]=DESC&filter[OWNER_ID]={deal["id"]}&select=*&select=COMMUNICATIONS",'
        # data_contacts = '''
        #                      {
        #                         "order": { "OWNER_ID": "DESC" },
        #                         "filter": {"OWNER_ID": 7717 },
        #                         "select": [ "*","COMMUNICATIONS"]
        #                     }
        #                 '''
        #
        # activity_test = self.post_from_url(f'{B24_URI}/crm.activity.list', data_contacts)


        # data_company = '''
        #              {
        #                 "order": { "DATE_CREATE": "ASC" },
        #                 "select": ["ID", "TITLE", "CURRENCY_ID", "REVENUE","PHONE","EMAIL","ADDRESS"]
        #             }
        #         '''
        # "crm.company.list",
        # {
        #     order: {"DATE_CREATE": "ASC"},
        #     filter: {"INDUSTRY": "MANUFACTURING", "COMPANY_TYPE": "CUSTOMER"},
        #     select: ["ID", "TITLE", "CURRENCY_ID", "REVENUE"]
        # },
        # companies = self.post_from_url(f'{B24_URI}/crm.company.list', data_company)
        # companies = None

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
                    # dict_users = self.get_username_activities()
                    if not dict_users:
                        dict_users = self.get_all_bitrix('user.get', {})

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
                        ENTITY_TYPE_ID = False
                        ENTITY_ID = False
                        if 'COMMUNICATIONS' in activity.keys():
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


                            date_deadline_fmt = self.date_deadline_tml.format(date_deadline_str=date_deadline_str)
                            company_fmt = self.company_tml.format(COMPANY_TITLE=COMPANY_TITLE,tel=tel,company_id=company_id)
                            responsible_user_fmt = self.responsible_user_tml.format(responsible_user_lastname=responsible_user_lastname)
                            partner_company_fmt = self.partner_company_tml.format(date_deadline_tml=date_deadline_fmt,
                                                        communication_name_tml='',
                                                        company_tml=company_fmt,
                                                        responsible_user_tml=responsible_user_fmt)


                        elif(ENTITY_TYPE_ID == 3):
                            partner_id = 0

                            if len(contacts) > 0:
                                contact = next((contact for contact in contacts if contact['ID'] == ENTITY_ID), False)
                                contact_name = "<p>Автор:" + contact['NAME'] + "&nbsp;" + (contact['LAST_NAME'] or '') + "</p>"

                            if contact:
                                partner_search = self.env['res.partner'].search([('name', 'like', (contact['LAST_NAME'] or '')),('name', 'like', contact['NAME'])])
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



                                date_deadline_fmt = self.date_deadline_tml.format(date_deadline_str=date_deadline_str)
                                communication_name_fmt = self.communication_name_tml.format(COMMUNICATIONS_NAME=COMMUNICATIONS_NAME,partner_id=partner_id, tel=tel)
                                company_fmt = self.company_tml.format(COMPANY_TITLE=COMPANY_TITLE, tel=tel,
                                                                      company_id=company_id)
                                responsible_user_fmt = self.responsible_user_tml.format(
                                    responsible_user_lastname=responsible_user_lastname)
                                partner_company_fmt = self.partner_company_tml.format(date_deadline_tml=date_deadline_fmt,
                                                                                  communication_name_tml=communication_name_fmt,
                                                                                  company_tml=company_fmt,
                                                                                  responsible_user_tml=responsible_user_fmt)

                            else:

                                date_deadline_fmt = self.date_deadline_tml.format(date_deadline_str=date_deadline_str)
                                responsible_user_fmt = self.responsible_user_tml.format(
                                    responsible_user_lastname=responsible_user_lastname)
                                partner_company_fmt = self.partner_company_tml.format(date_deadline_tml=date_deadline_fmt,
                                                                                  communication_name_tml='',
                                                                                  company_tml='',
                                                                                  responsible_user_tml=responsible_user_fmt)

                        else:
                            if 'COMMUNICATIONS' in activity.keys():
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

                                date_deadline_fmt = self.date_deadline_tml.format(date_deadline_str=date_deadline_str)
                                communication_name_fmt = self.communication_name_tml.format(
                                    COMMUNICATIONS_NAME=COMMUNICATIONS_NAME, partner_id=partner_id, tel=tel)
                                company_fmt = self.company_tml.format(COMPANY_TITLE=COMPANY_TITLE, tel=tel,
                                                                      company_id=company_id)
                                responsible_user_fmt = self.responsible_user_tml.format(
                                    responsible_user_lastname=responsible_user_lastname)
                                partner_company_fmt = self.partner_company_tml.format(date_deadline_tml=date_deadline_fmt,
                                                                                  communication_name_tml=communication_name_fmt,
                                                                                  company_tml=company_fmt,
                                                                                  responsible_user_tml=responsible_user_fmt)
                            else:
                                temp_var = 0

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

                        note = (activity['DESCRIPTION'] or '') +res_user_last_name+ partner_company_fmt
                        summary = activity['SUBJECT']
                        if (activity['PROVIDER_TYPE_ID'] == "CALL"):
                            summary = re.sub('(на.+(\d+\s\d+))|(на.+\d+)|(від.+(\d+\s\d+))', ' дзвінок', activity['SUBJECT'])
                            # note = re.sub('(Вихідний на.+(\d+\s\d+))|(на.+\d+)|(Вхідний від.+(\d+\s\d+))','',note)
                        elif(activity['PROVIDER_TYPE_ID'] =="2"):
                            note = ' '
                        elif (activity['PROVIDER_TYPE_ID'] == "EMAIL"):
                            note = re.sub('(Наші інфопартнери.+>)|(<img.+>)|(З повагою.*)(.*\n)*(.*)*', '', note)

                        if (activity['PROVIDER_TYPE_ID'] == "CALL"):
                            activity_typ = 'mail.mail_activity_data_call'
                        elif (activity['PROVIDER_TYPE_ID'] == "EMAIL"):
                            activity_typ = 'mail.mail_activity_data_email'
                        elif (activity['PROVIDER_TYPE_ID'] == "TASK"):
                            activity_typ = 'mail.mail_activity_data_todo'
                        else:
                            activity_typ = None


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


                                attachment_obj = self.env['ir.attachment'].create({
                                    'name': phone_f_name,
                                    'datas': req_out,
                                    'type': 'binary',
                                    'mimetype': 'audio/mpeg',
                                })
                                attachment.append(attachment_obj.id)

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
                        # if create_date < last_update_date: create_date = last_update_date


                        if activity['COMPLETED'] == 'Y':
                            message_id = act_env.action_feedback(feedback=' ')
                            act_to_message = self.env['mail.message'].browse([message_id])
                            act_to_message.write({'date': create_date, 'author_id': user_id, 'attachment_ids':attachment})

        return 1


    def action_import_activities_comments(self):
        # bitrix_hook_url = self.env['ir.config_parameter'].sudo().get_param('biko_load_comments.bitr_url')
        # if not bitrix_hook_url:
        #     raise UserError(_("Module requires parameter in Settings '%s' ", 'Bitrix Webhook Url'))
        # global B24_URI
        # B24_URI = bitrix_hook_url

        self.action_import_records()
        # print('import_records--------------:) ')
        self.action_import_activities()
        # print('import_activities============:) ')






