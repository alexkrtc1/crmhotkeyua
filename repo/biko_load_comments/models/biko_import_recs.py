from odoo import models, fields, api, modules, sql_db, _
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
from odoo.tests.common import get_db_name

hk_logger = logging.getLogger(__name__)


B24_URI = ''
# B24_URI = get_config_bitrix('biko_load_comments.bitr_url')
hk_logger.info('hotkey get_config_bitrix :' + B24_URI)

contacts = False
dict_users = False
relpath = os.path.dirname(os.path.realpath(__file__))

headers = CaseInsensitiveDict()
headers["Content-Type"] = "application/json"


class ImportComments(models.Model):
    _inherit = 'crm.lead'


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
                        <a href=# data-oe-model=res.users data-oe-id={user_id_tml} class="crm-timeline__card_link --bold">
                         {responsible_user_lastname}</a>
                    </div>
            </div>
        '''

    def hello(self):
        deals = dict()
        selected = self.env.context["active_ids"]
        try:
            # ref = self.env['ir.model.data'].search([('name', '=', 'crm_lead_BXDeal_9382')])
            ref = self.env['ir.model.data'].search(
                [('res_id', 'in', selected), ('name', 'like', 'crm_lead_BXDeal_%'), ('model', '=', 'crm.lead')])

            for r in ref:
                ref_id = r.name.split('crm_lead_BXDeal_')[1]
                rname = r.name
                rmodule = r.module
                deals.update({ref_id: {'id': ref_id, 'external_id': rmodule + '.' + rname, 'comments': dict(),
                                       'activities': dict()}})

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
                                    deal['comments'][comment_line['ID']]['FILES'][file]['urlDownload'] = res_file[
                                        'DOWNLOAD_URL'];

                                    # for c in deal['comments'].values():
                                    #     if 'FILES' in c.keys():
                                    #         for f in c['FILES']:
                                    #             DOWNLOAD_URL = f['urlDownload'];

        return [deals, deals_with_files]

    def get_activities(self, deals):
        param_http_activity =''
        allow_planned_activity = bool(
            self.env['ir.config_parameter'].sudo().get_param('biko_load_comments.allow_activity'))
        param_http_activity = not allow_planned_activity and '&filter[COMPLETED]=YES' or ''


        deals_with_files = {}

        templ_start = '{"halt":0,"cmd": {'
        templ_end = '}}'
        i = 0
        ir = 0
        packages = []
        req_str = ""


        for deal in deals.values():
            req_str += f'"ac1_{deal["id"]}":"crm.activity.list?order[CREATED]=DESC' \
                       f'&filter[OWNER_ID]={deal["id"]}&filter[OWNER_TYPE_ID]=2' \
                       f'&select[]=*&select[]=COMMUNICATIONS",' \
                       f'"con_{deal["id"]}": "crm.deal.contact.items.get?id={deal["id"]}",' \
                       f'"acc_{deal["id"]}":"crm.activity.list?filter[OWNER_TYPE_ID]=3&filter[OWNER_ID]=$result[con_{deal["id"]}][0][CONTACT_ID]{param_http_activity}&select[]=*&select[]=COMMUNICATIONS",'

            if ((ir + 1) % 48 == 0) or (i == len(deals) - 1):
                json_res = json.loads(templ_start + req_str[0:-1] + templ_end)
                packages.append(json_res)
                req_str = ""

            i += 1
            ir += 3

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
                    if deal_id[0]=='a':
                        did = deal_id[4:]
                        deal = deals[did]
                        for activity_line in activity:
                            if activity_line['COMPLETED'] == 'N':
                                deal['activities'].update({activity_line['ID']: activity_line})
                            elif activity_line['COMPLETED'] == 'Y':
                                deal['comments'].update({activity_line['ID']: activity_line})

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
            allow_planned_activity = bool(
                self.env['ir.config_parameter'].sudo().get_param('biko_load_comments.allow_activity'))
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

    def get_all_bitrix(self, method, params):
        global b
        entity_list = b.get_all(method, params=params)
        return entity_list

    def get_username_activities(self):
        bitrix_user = {'lastname': ''}
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
        session = requests.Session()

        req =session.post(url, param, headers=pheaders)

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
            param_str = json.dumps(param_dict, ensure_ascii=False)
            req = session.post(url, param_str, headers=pheaders)
            resp_json = req.json()
            res.extend(resp_json['result'])
            i += 1

        session.close()
        hk_logger.info("post_from_url url=%s i=%s", url, i)
        return res

    def action_import_records(self, deals):
        # deals = self.get_deals()
        # deals = self.hello()
        if len(deals) == 0:
            print('Error while loading deals!')
            return

        deals_res, deals_with_files = self.get_comments(deals)
        # deals_res = self.get_activities(deals_res)

        env_deals = self.env['crm.lead'].env
        odoobot_id = self.env['ir.model.data'].xmlid_to_res_id("base.partner_root")


        for deal in deals_res.values():

            comments_list = deal['comments']
            sorted_comments_date = sorted(list(comments_list.values()),
                                 key=lambda x: (datetime.strptime(
                                     str(datetime.fromisoformat(x['CREATED']).replace(tzinfo=None)),
                                     '%Y-%m-%d %H:%M:%S')))
            dict_users = self.get_username_activities()
            # activity_list = deal['activities']

            external_id = deal['external_id']
            id = deal['id']
            # user_id = self.env['res.users'].search(['id', '=', 11])
            # record = env_deals.ref('__import__.' + external_id)
            record = env_deals.ref(external_id)
            #
            if record:
                if comments_list:
                    for comment in sorted_comments_date:
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
                        message_rec = record.message_post(body=msg, author_id=user_id, message_type='comment',
                                                          attachments=f_attachments)
                        message_rec['date'] = date_time

    def action_import_activities(self, deals):
        # deals = self.hello()
        if len(deals) == 0:
            print('Error while loading deals!')
            return

        # deals_res = self.get_activities_bitrix(deals)
        deals_res, deals_with_files = self.get_comments(deals)
        deals_res = self.get_activities(deals_res)

        # data_contacts = {
        #     # "order": { "DATE_CREATE": "ASC" },
        #     "select": ["ID", "NAME", "LAST_NAME", "LEAD_ID", "COMPANY_ID", "EMAIL", "PHONE", "TYPE_ID"]
        # }
        data_contacts = '''
        {
            "select": ["ID", "NAME", "LAST_NAME", "LEAD_ID", "COMPANY_ID", "EMAIL", "PHONE", "TYPE_ID"]
        }
        '''

        global contacts
        global dict_users

        if not contacts:
            # contacts = self.get_all_bitrix('crm.contact.list', data_contacts)
            contacts = self.post_from_url(f'{B24_URI}/crm.contact.list', data_contacts)

        if not dict_users:
            dict_users = self.post_from_url(f'{B24_URI}/user.get', '{}')

        # test activity
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

        ##########
        def comment_activity_lists(activity):
            res_user_last_name = ''
            # nonlocal record
            # nonlocal activity_list
            nonlocal partner_company_fmt
            nonlocal note
            nonlocal summary
            nonlocal activity_typ
            nonlocal create_date
            nonlocal user_id
            nonlocal user_id_tml
            nonlocal responsible_id
            nonlocal date_deadline
            # if record:
            if activity:
                # dict_users = self.get_username_activities()
                # if not dict_users:
                #     dict_users = self.get_all_bitrix('user.get', {})

                # sorted_date = sorted(list(activity_comments_list.values()),
                #                      key=lambda x: (datetime.strptime(
                #                          str(datetime.fromisoformat(x['CREATED']).replace(tzinfo=None)),
                #                          '%Y-%m-%d %H:%M:%S')))

                # datetime.strptime(str(datetime.fromisoformat(list(activity_list.values())[1]['CREATED']).replace(tzinfo=None)),'%Y-%m-%d %H:%M:%S')

                # for activity in activity_list.values():
                # for activity in sorted_date:
                if 'OWNER_ID' in activity.keys():
                    date_deadline = datetime.fromisoformat(activity['DEADLINE']).replace(tzinfo=None)
                    date_deadline_str = date_deadline.strftime("%A,%d%b %Y,%H:%M")
                    create_date = datetime.fromisoformat(activity['CREATED']).replace(tzinfo=None)
                    last_update_date = datetime.fromisoformat(activity['LAST_UPDATED']).replace(tzinfo=None)
                    # message = locale_date_str + " тел:" + partner_phone + " Только что был пропущен звонок от" + partner_name + "<a href=# data-oe-model=crm.phonecall data-oe-id=%d>#%s - Ссылка на звонок</a>" % (record.id, record.name)
                    author_id = activity['AUTHOR_ID']
                    responsible_id = activity['RESPONSIBLE_ID']
                    ENTITY_TYPE_ID = False
                    ENTITY_ID = False
                    partner_company_fmt = ''
                    if 'COMMUNICATIONS' in activity.keys():
                        if len(activity['COMMUNICATIONS']) > 0:
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
                        responsible_user_lastname = responsible_user['NAME'] + ' ' + responsible_user['LAST_NAME']

                    if len(dict_users) > 0:
                        res_user = next((user for user in dict_users if user['ID'] == author_id), False)
                        res_user_last_name = "<p>Автор:" + res_user['NAME'] + "&nbsp;" + res_user[
                            'LAST_NAME'] + "</p>"

                    if res_user:
                        user_search = self.env['res.users'].search([('name', 'like', res_user['LAST_NAME'])])
                        if user_search:
                            user_id = user_search[0].partner_id.id
                            user_id_tml = user_search[0].id
                        else:
                            user_id = odoobot_id
                            user_id_tml = odoobot_user_id
                    # <a href=# data-oe-model=account.move data-oe-id={move_id}>{move_name}</a>"

                    if ENTITY_TYPE_ID:
                        if (ENTITY_TYPE_ID == 4):
                            COMPANY_ID = ENTITY_ID
                            COMPANY_TITLE = ''
                            # company_id = 0
                            if 'COMMUNICATIONS' in activity.keys():
                                if len(activity['COMMUNICATIONS']) > 0:
                                    if (len(activity['COMMUNICATIONS'][0]['ENTITY_SETTINGS']) > 0):
                                        COMPANY_TITLE = activity['COMMUNICATIONS'][0]['ENTITY_SETTINGS'][
                                            'COMPANY_TITLE']

                            if COMPANY_TITLE:
                                company_search = self.env['res.partner'].search(
                                    [('name', 'like', COMPANY_TITLE)])
                                if company_search:
                                    company_id = company_search[0].id or 0
                                    url_company = f'web#id={company_id}&model=res.partner'

                            date_deadline_fmt = self.date_deadline_tml.format(date_deadline_str=date_deadline_str)
                            company_fmt = self.company_tml.format(COMPANY_TITLE=COMPANY_TITLE, tel=tel,
                                                                  company_id=company_id)
                            responsible_user_fmt = self.responsible_user_tml.format(user_id_tml=user_id_tml,
                                responsible_user_lastname=responsible_user_lastname)
                            partner_company_fmt = self.partner_company_tml.format(
                                date_deadline_tml=date_deadline_fmt,
                                communication_name_tml='',
                                company_tml=company_fmt,
                                responsible_user_tml=responsible_user_fmt)

                        elif (ENTITY_TYPE_ID == 3):
                            partner_id = 0
                            COMMUNICATIONS_NAME = ''
                            COMPANY_TITLE = ''

                            if len(contacts) > 0:
                                contact = next((contact for contact in contacts if contact['ID'] == ENTITY_ID),
                                               False)
                                # contact_name = "<p>Автор:" + contact['NAME'] + "&nbsp;" + (
                                #         contact['LAST_NAME'] or '') + "</p>"

                                if contact:
                                    partner_search = self.env['res.partner'].search(
                                        [('name', 'like', (contact['LAST_NAME'] or '')),
                                         ('name', 'like', contact['NAME'])])
                                    if partner_search:
                                        partner_id = partner_search[0].id or 0
                                        url_partner = f'web#id={partner_id}&model=res.partner'

                            if 'COMMUNICATIONS' in activity.keys():
                                if len(activity['COMMUNICATIONS']) > 0:
                                    if (len(activity['COMMUNICATIONS'][0]['ENTITY_SETTINGS']) > 0):
                                        COMMUNICATIONS_NAME = activity['COMMUNICATIONS'][0]['ENTITY_SETTINGS'][
                                                                  'NAME'] + ' ' + \
                                                              activity['COMMUNICATIONS'][0]['ENTITY_SETTINGS'][
                                                                  'LAST_NAME'] or ''

                                        COMMUNICATIONS_LAST_NAME = activity['COMMUNICATIONS'][0]['ENTITY_SETTINGS'][
                                            'LAST_NAME']
                                        if 'COMPANY_TITLE' in activity['COMMUNICATIONS'][0]['ENTITY_SETTINGS'].keys():
                                            COMPANY_TITLE = activity['COMMUNICATIONS'][0]['ENTITY_SETTINGS'][
                                            'COMPANY_TITLE']
                                        if 'COMPANY_ID' in activity['COMMUNICATIONS'][0]['ENTITY_SETTINGS'].keys():
                                            COMPANY_ID = activity['COMMUNICATIONS'][0]['ENTITY_SETTINGS']['COMPANY_ID']

                                        if COMPANY_TITLE:
                                            company_search = self.env['res.partner'].search(
                                                [('name', 'like', COMPANY_TITLE)])
                                            if company_search:
                                                company_id = company_search[0].id or 0
                                                url_company = f'web#id={company_id}&model=res.partner'

                                        date_deadline_fmt = self.date_deadline_tml.format(
                                            date_deadline_str=date_deadline_str)
                                        communication_name_fmt = self.communication_name_tml.format(
                                            COMMUNICATIONS_NAME=COMMUNICATIONS_NAME, partner_id=partner_id, tel=tel)
                                        company_fmt = self.company_tml.format(COMPANY_TITLE=COMPANY_TITLE, tel=tel,
                                                                              company_id=company_id)
                                        responsible_user_fmt = self.responsible_user_tml.format(user_id_tml=user_id_tml,
                                            responsible_user_lastname=responsible_user_lastname)
                                        partner_company_fmt = self.partner_company_tml.format(
                                            date_deadline_tml=date_deadline_fmt,
                                            communication_name_tml=communication_name_fmt,
                                            company_tml=company_fmt,
                                            responsible_user_tml=responsible_user_fmt)

                            else:

                                date_deadline_fmt = self.date_deadline_tml.format(
                                    date_deadline_str=date_deadline_str)
                                responsible_user_fmt = self.responsible_user_tml.format(user_id_tml=user_id_tml,
                                    responsible_user_lastname=responsible_user_lastname)
                                partner_company_fmt = self.partner_company_tml.format(
                                    date_deadline_tml=date_deadline_fmt,
                                    communication_name_tml='',
                                    company_tml='',
                                    responsible_user_tml=responsible_user_fmt)

                        else:
                            COMMUNICATIONS_NAME = ''
                            COMPANY_TITLE = ''
                            if 'COMMUNICATIONS' in activity.keys():
                                if len(activity['COMMUNICATIONS']) > 1:
                                    if (len(activity['COMMUNICATIONS'][1]['ENTITY_SETTINGS']) > 0):

                                        COMMUNICATIONS_NAME = activity['COMMUNICATIONS'][1]['ENTITY_SETTINGS']['NAME'] + ' ' + \
                                                              activity['COMMUNICATIONS'][1]['ENTITY_SETTINGS']['LAST_NAME'] or ''

                                        COMMUNICATIONS_LAST_NAME = activity['COMMUNICATIONS'][1]['ENTITY_SETTINGS'][
                                            'LAST_NAME']


                                        if 'COMPANY_TITLE' in activity['COMMUNICATIONS'][1]['ENTITY_SETTINGS'].keys():
                                            COMPANY_TITLE = activity['COMMUNICATIONS'][1]['ENTITY_SETTINGS']['COMPANY_TITLE']

                                        if 'COMPANY_ID' in activity['COMMUNICATIONS'][1]['ENTITY_SETTINGS'].keys():
                                            COMPANY_ID = activity['COMMUNICATIONS'][1]['ENTITY_SETTINGS']['COMPANY_ID']

                                        ENTITY_TYPE_ID = int(activity['COMMUNICATIONS'][1]['ENTITY_TYPE_ID'])
                                        ENTITY_ID = activity['COMMUNICATIONS'][1]['ENTITY_ID']

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
                                    contact = next((contact for contact in contacts if contact['ID'] == ENTITY_ID),
                                                   False)
                                    # contact_name = "<p>Автор:" + contact['NAME'] + "&nbsp;" + (contact['LAST_NAME'] or '') + "</p>"

                                    if contact:
                                        partner_search = self.env['res.partner'].search(
                                            [('name', 'like', (contact['LAST_NAME'] or '')),
                                             ('name', 'like', contact['NAME'])])
                                        if partner_search:
                                            partner_id = partner_search[0].id or 0
                                            url_partner = f'web#id={partner_id}&model=res.partner'

                                date_deadline_fmt = self.date_deadline_tml.format(
                                    date_deadline_str=date_deadline_str)
                                communication_name_fmt = self.communication_name_tml.format(
                                    COMMUNICATIONS_NAME=COMMUNICATIONS_NAME, partner_id=partner_id, tel=tel)
                                company_fmt = self.company_tml.format(COMPANY_TITLE=COMPANY_TITLE, tel=tel,
                                                                      company_id=company_id)
                                responsible_user_fmt = self.responsible_user_tml.format(user_id_tml=user_id_tml,
                                    responsible_user_lastname=responsible_user_lastname)
                                partner_company_fmt = self.partner_company_tml.format(
                                    date_deadline_tml=date_deadline_fmt,
                                    communication_name_tml=communication_name_fmt,
                                    company_tml=company_fmt,
                                    responsible_user_tml=responsible_user_fmt)
                            else:
                                temp_var = 0

                    if res_user:
                        user_search = self.env['res.users'].search([('name', 'like', res_user['LAST_NAME'])])
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

                    note = (activity['DESCRIPTION'] or '') + res_user_last_name + partner_company_fmt
                    note1 = re.sub(r'\[', '<', note)
                    note = re.sub(r'\]', '>', note1)
                    summary = activity['SUBJECT']


                    if activity['COMPLETED'] == 'Y':
                        if (activity['PROVIDER_TYPE_ID'] == "CALL"):
                            summary = re.sub('(на.+(\d+\s\d+))|(на.+\d+)|(від.+(\d+\s\d+))', ' дзвінок',
                                             activity['SUBJECT'])
                            # note = re.sub('(Вихідний на.+(\d+\s\d+))|(на.+\d+)|(Вхідний від.+(\d+\s\d+))','',note)
                            body_message = '<p><span class ="fa fa-phone fa-fw"> </span> <span> Call </span> done   </p>'
                            note = f"{body_message}{note}"

                        elif (activity['PROVIDER_TYPE_ID'] == "2"):
                            note = ' '
                        elif (activity['PROVIDER_TYPE_ID'] == "EMAIL"):
                            note = re.sub('(Наші інфопартнери.+>)|(<img.+>)|(З повагою.*)(.*\n)*(.*)*', '', note)

                        if (activity['PROVIDER_TYPE_ID'] == "CALL"):
                            activity_typ = 'comment'
                        elif (activity['PROVIDER_TYPE_ID'] == "EMAIL"):
                            activity_typ = 'email'
                        elif (activity['PROVIDER_TYPE_ID'] == "TASK"):
                            body_message = '<p><span class ="fa fa-tasks fa-fw"></span> <span> To Do </span>done<span>:</span></p>'
                            note = f"{body_message}{note}"
                            activity_typ = 'comment'
                        elif (activity['PROVIDER_TYPE_ID'] == "MEETING"):
                            body_message = '<p><span class ="fa fa-users fa-fw"></span><span> Meeting </span>done<span>:</span></p>'
                            note = f"{body_message}{note}"
                            activity_typ = 'comment'
                        else:
                            activity_typ = 'comment'

                    # [
                    #     ('email', 'Email'),
                    #     ('comment', 'Comment'),
                    #     ('notification', 'System notification'),
                    #     ('user_notification', 'User Specific Notification')]
                    if activity['COMPLETED'] == 'N':
                        if (activity['PROVIDER_TYPE_ID'] == "CALL"):
                            summary = re.sub('(на.+(\d+\s\d+))|(на.+\d+)|(від.+(\d+\s\d+))', ' дзвінок',
                                             activity['SUBJECT'])
                            # note = re.sub('(Вихідний на.+(\d+\s\d+))|(на.+\d+)|(Вхідний від.+(\d+\s\d+))','',note)
                        elif (activity['PROVIDER_TYPE_ID'] == "2"):
                            note = ' '
                        elif (activity['PROVIDER_TYPE_ID'] == "EMAIL"):
                            note = re.sub('(Наші інфопартнери.+>)|(<img.+>)|(З повагою.*)(.*\n)*(.*)*', '', note)

                        if (activity['PROVIDER_TYPE_ID'] == "CALL"):
                            activity_typ = 'mail.mail_activity_data_call'
                        elif (activity['PROVIDER_TYPE_ID'] == "EMAIL"):
                            activity_typ = 'mail.mail_activity_data_email'
                        elif (activity['PROVIDER_TYPE_ID'] == "TASK"):
                            activity_typ = 'mail.mail_activity_data_todo'
                        elif (activity['PROVIDER_TYPE_ID'] == "MEETING"):
                            activity_typ = 'mail_activity_data_meeting'
                        else:
                            activity_typ = None

                    phone_file_attachments = []
                    attachment = []
                    # if ('FILES' in activity.keys()):
                    #     for phone_file in activity['FILES']:
                    #         #
                    #         file_id = {'id': phone_file['id']}
                    #         req_file = requests.post(f'{B24_URI}/disk.file.get', json=file_id)
                    #         if req_file.status_code != 200:
                    #             print('Error accessing to file B24!')
                    #             continue
                    #
                    #         resp_file_json = req_file.json()
                    #         res_file = resp_file_json['result']
                    #
                    #         if len(res_file) > 0:
                    #             download_url = res_file['DOWNLOAD_URL']
                    #             download_url = download_url.replace('\\', '')
                    #         #
                    #         phone_f_name = str(phone_file['id']) + '.mp3'
                    #         headers = {'Content-Type': 'audio/mpeg'}
                    #         # req = requests.get(phone_file['url'], headers = headers)
                    #         req = requests.get(download_url, headers=headers)
                    #         req_out = base64.b64encode(req.content).decode('utf-8')
                    #         phone_file_attachments.append((phone_f_name, req.content))
                    #         #
                    #
                    #         attachment_obj = self.env['ir.attachment'].create({
                    #             'name': phone_f_name,
                    #             'datas': req_out,
                    #             'type': 'binary',
                    #             'mimetype': 'audio/mpeg',
                    #         })
                    #         attachment.append(attachment_obj.id)

                    # act_env = record.activity_schedule(activity_typ, user_id=su_id, date_deadline=date_deadline,
                    #                                    summary=summary, note=note)
                    # act_env['create_date'] = create_date
                    # act_env['create_uid'] = responsible_id

                    # act_env_id = act_env.res_id
                    # act_note = act_env.note
                    # if create_date < last_update_date: create_date = last_update_date

                    # if activity['COMPLETED'] == 'Y':
                    #     message_id = act_env.action_feedback(feedback=' ')
                    #     act_to_message = self.env['mail.message'].browse([message_id])
                    #     act_to_message.write(
                    #         {'date': create_date, 'author_id': user_id, 'attachment_ids': attachment})
                else:
                    activity_typ = 'comment'
                    user_id = False
                    create_date = datetime.fromisoformat(comment['CREATED']).replace(tzinfo=None)
                    # note = comment['COMMENT'] + res_user_last_name + partner_company_fmt
                    # date_deadline_fmt = self.date_deadline_tml.format(
                    #     date_deadline_str=date_deadline_str)
                    # communication_name_fmt = self.communication_name_tml.format(
                    #     COMMUNICATIONS_NAME=COMMUNICATIONS_NAME, partner_id=partner_id, tel=tel)
                    # company_fmt = self.company_tml.format(COMPANY_TITLE=COMPANY_TITLE, tel=tel,
                    #                                       company_id=company_id)

                    author_id = comment['AUTHOR_ID']
                    if len(dict_users) > 0:
                        res_user = next((user for user in dict_users if user['ID'] == author_id), False)
                        res_user_last_name = res_user['NAME'] + "&nbsp;" + res_user[
                            'LAST_NAME']

                    if res_user:
                        user_search = self.env['res.users'].search([('name', 'like', res_user['LAST_NAME'])])
                        if user_search:
                            user_id = user_search[0].partner_id.id
                            user_id_tml = user_search[0].id
                        else:
                            user_id = odoobot_id

                    responsible_user_tml = self.responsible_user_tml
                    responsible_user_tml = re.sub('(?<=<div class=\"crm-timeline__card-container_info-title\">)[\s,\w]*', 'Автор:',
                                     responsible_user_tml, flags=re.I | re.UNICODE)

                    responsible_user_fmt = responsible_user_tml.format(user_id_tml=user_id_tml,
                        responsible_user_lastname=res_user_last_name)
                    partner_company_fmt = self.partner_company_tml.format(
                        date_deadline_tml='',
                        communication_name_tml='',
                        company_tml='',
                        responsible_user_tml=responsible_user_fmt)
                    note = comment['COMMENT']
                    note1 = re.sub(r'\[', '<', note)
                    note = re.sub(r'\]', '>', note1)
                    note += partner_company_fmt
                    body_message = '<p><span class ="fa fa-commenting" style="color: #2fc6f6;"></span> <span> Comment </span><span>:</span></p>'
                    # <i class ="fa-regular fa-message-captions" style="color: #274c8b;"> </i>
                    note = f"{body_message}{note}"
                    ###
                    # message_rec = record.message_post(body=msg, author_id=user_id, message_type='comment',
                    #                                   attachments=f_attachments)
                    # message_rec['date'] = date_time
        # end def comment_activity_lists()


        ##########

        # author_id = comment['AUTHOR_ID']
        # if len(dict_users) > 0:
        #     res_user = next((user for user in dict_users if user['ID'] == author_id), False)
        #
        # if res_user:
        #     user_search = self.env['res.users'].search([('name', 'like', res_user['LAST_NAME'])])
        #     if user_search:
        #         user_id = user_search[0].partner_id.id
        #     else:
        #         user_id = odoobot_id
        # message_rec = record.message_post(body=msg, author_id=user_id, message_type='comment',
        #                                   attachments=f_attachments)
        # message_rec['date'] = date_time
        ########## json.dumps(comments_list,ensure_ascii=False)
        for deal in deals_res.values():
            activity_list = deal['activities']
            comments_list = deal['comments']
            sorted_comments_date = sorted(list(comments_list.values()),
                                 key=lambda x: (datetime.strptime(
                                     str(datetime.fromisoformat(x['CREATED']).replace(tzinfo=None)),
                                     '%Y-%m-%d %H:%M:%S')))
            external_id = deal['external_id']
            id = deal['id']
            record = env_deals.ref(external_id)
            partner_company_fmt = ''
            note = ''
            summary = ''
            activity_typ = ''
            create_date = False
            user_id = False
            user_id_tml = False
            responsible_id = False
            date_deadline = False

            if record:
                record = env_deals.ref(external_id)
                ###########
                if comments_list:
                    # dict_users = self.get_username_activities()

                    for comment in sorted_comments_date:
                        # if comment["ID"]=='170414':
                        #     hk_logger.warning('comment["ID"] = %s', str(comment['ID']))
                        # hk_logger.warning('comment["ID"] = %s', str(comment['ID']))
                        # if comment['ID']== '68467':
                        #     hk_logger.info('yes comment["ID"] = %s',  str(comment['ID']))
                        #######################################
                        partner_company_fmt = ''
                        note = ''
                        summary = ''
                        activity_typ = ''
                        create_date = False
                        user_id = False
                        user_id_tml = False
                        responsible_id = False
                        date_deadline = False
                        comment_activity_lists(comment)

                        note = '<div>'+summary+'</div>'+note

                        ######################################
                        # date_time = datetime.fromisoformat(comment['CREATED']).replace(tzinfo=None)
                        # msg = comment['COMMENT']
                        f_attachments = []
                        # if ('FILES' in comment.keys()):
                        #     for c_file in comment['FILES'].values():
                        #         f_name = c_file['name']
                        #         req = requests.get(c_file['urlDownload'])
                        #
                        #         f_attachments.append((f_name, req.content))

                        # author_id = comment['AUTHOR_ID']
                        # if len(dict_users) > 0:
                        #     res_user = next((user for user in dict_users if user['ID'] == author_id), False)
                        #
                        # if res_user:
                        #     user_search = self.env['res.users'].search([('name', 'like', res_user['LAST_NAME'])])
                        #     if user_search:
                        #         user_id = user_search[0].partner_id.id
                        #     else:
                        #         user_id = odoobot_id
                        message_rec = record.message_post(body=note, author_id=user_id, message_type=activity_typ,
                                                          attachments=f_attachments)
                        message_rec['date'] = create_date



                ###############

                if activity_list:
                    # dict_users = self.get_username_activities()
                    # if not dict_users:
                    #     dict_users = self.get_all_bitrix('user.get', {})

                    sorted_date = sorted(list(activity_list.values()),
                                         key=lambda x: (datetime.strptime(
                                             str(datetime.fromisoformat(x['CREATED']).replace(tzinfo=None)),
                                             '%Y-%m-%d %H:%M:%S')))

                    # datetime.strptime(str(datetime.fromisoformat(list(activity_list.values())[1]['CREATED']).replace(tzinfo=None)),'%Y-%m-%d %H:%M:%S')

                    # for activity in activity_list.values():
                    for activity in sorted_date:
                        partner_company_fmt = ''
                        note = ''
                        summary = ''
                        activity_typ = ''
                        create_date = False
                        user_id = False
                        user_id_tml = False
                        responsible_id = False
                        date_deadline = False
                        comment_activity_lists(activity)


                        phone_file_attachments = []
                        attachment = []
                        # if ('FILES' in activity.keys()):
                        #     for phone_file in activity['FILES']:
                        #         #
                        #         file_id = {'id': phone_file['id']}
                        #         req_file = requests.post(f'{B24_URI}/disk.file.get', json=file_id)
                        #         if req_file.status_code != 200:
                        #             print('Error accessing to file B24!')
                        #             continue
                        #
                        #         resp_file_json = req_file.json()
                        #         res_file = resp_file_json['result']
                        #
                        #         if len(res_file) > 0:
                        #             download_url = res_file['DOWNLOAD_URL']
                        #             download_url = download_url.replace('\\', '')
                        #         #
                        #         phone_f_name = str(phone_file['id']) + '.mp3'
                        #         headers = {'Content-Type': 'audio/mpeg'}
                        #         # req = requests.get(phone_file['url'], headers = headers)
                        #         req = requests.get(download_url, headers=headers)
                        #         req_out = base64.b64encode(req.content).decode('utf-8')
                        #         phone_file_attachments.append((phone_f_name, req.content))
                        #         #
                        #
                        #         attachment_obj = self.env['ir.attachment'].create({
                        #             'name': phone_f_name,
                        #             'datas': req_out,
                        #             'type': 'binary',
                        #             'mimetype': 'audio/mpeg',
                        #         })
                        #         attachment.append(attachment_obj.id)

                        act_env = record.activity_schedule(activity_typ, user_id=user_id_tml, date_deadline=date_deadline,
                                                           summary=summary, note=note)
                        act_env['create_date'] = create_date
                        act_env['create_uid'] = responsible_id

                        act_env_id = act_env.res_id
                        act_note = act_env.note


                        if activity['COMPLETED'] == 'Y':
                            message_id = act_env.action_feedback(feedback=' ')
                            act_to_message = self.env['mail.message'].browse([message_id])
                            act_to_message.write(
                                {'date': create_date, 'author_id': user_id, 'attachment_ids': attachment})


        return 1

    def action_import_activities_comments(self):
        bitrix_hook_url = self.env['ir.config_parameter'].sudo().get_param('biko_load_comments.bitr_url')
        if not bitrix_hook_url:
            raise UserError(_("Module requires parameter in Settings '%s' ", 'biko_load_comments.bitr_url'))
        global B24_URI
        B24_URI = bitrix_hook_url

        deals_selected = self.hello()
        # self.action_import_records(deals_selected)
        # hk_logger.info('import_records--------------:) ')
        self.action_import_activities(deals_selected)
        hk_logger.info('import_activities============:) ')

