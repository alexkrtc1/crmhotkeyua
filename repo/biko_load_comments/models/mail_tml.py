partner_company = '''
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
