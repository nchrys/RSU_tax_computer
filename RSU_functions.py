import pandas as pd
import datetime as datetime
import numpy as np
import copy

from dateutil.relativedelta import relativedelta

tax_info_dict = {'TMI_IR': 0.3, 'cotisation': 0.172, 'flat_tax_plus_value': 0.3}

# ./RSU_tax_helper/
taux = pd.read_csv('Euro_exchange.csv')
criteo_stock = pd.read_csv('HistoricalData_1647369022625.csv')
criteo_stock['stock_price'] = criteo_stock['Open'].apply(lambda x: float(x[1:]))
criteo_stock['date_dt'] = criteo_stock.Date.apply(
    lambda x: datetime.datetime.strptime(x, '%m/%d/%Y').strftime('%d/%m/%Y'))
exchange_rate_dict = taux.set_index('Date')['USD'].to_dict()
criteo_stock_dict = criteo_stock.set_index('date_dt')['stock_price'].to_dict()


def get_value_on_date(dt, value_dict):
    i = 0
    while (dt.strftime('%d/%m/%Y') not in value_dict.keys()) and (i < 10):
        dt = dt + datetime.timedelta(days=1)
        i += 1
    if i == 10:
        raise KeyError('check your date, no data in 10 days')
    return value_dict[dt.strftime('%d/%m/%Y')]


def get_stock_price_euro(dt, criteo_stock_dict=criteo_stock_dict,
                         exchange_rate_dict=exchange_rate_dict):
    stock_price_usd = get_value_on_date(dt, criteo_stock_dict)
    return stock_price_usd / get_value_on_date(dt, exchange_rate_dict)


def get_stock_price_euro_from_price_in_USD(dt, stock_price_USD,
                                           exchange_rate_dict=exchange_rate_dict):
    return stock_price_USD / get_value_on_date(dt, exchange_rate_dict)


def compute_rebate(selling_date_dt, vesting_date_dt, macron_law_id):
    if macron_law_id == 3:
        return 0.5
    elif relativedelta(selling_date_dt, vesting_date_dt).years < 2:
        return 0
    elif relativedelta(selling_date_dt, vesting_date_dt).years < 8:
        return 0.5
    else:
        return 0.65


# The more than 300k is not handled yet, if you did sell more than 300k of action do not rely
def compute_tax_info_from_matched_transaction(selling_date_dt, vesting_date_dt,
                                              selling_price_USD,
                                              macron_law_id=0,
                                              tax_info_dict=tax_info_dict,
                                              criteo_stock_dict=criteo_stock_dict,
                                              exchange_rate_dict=exchange_rate_dict):
    vesting_price = get_stock_price_euro(vesting_date_dt)
    selling_price = get_stock_price_euro_from_price_in_USD(selling_date_dt,
                                                           selling_price_USD)
      # for now as I don't handle the 300k, does not change anything
    if selling_price >= vesting_price:
        plus_value = selling_price - vesting_price
        vesting_price_with_moins_value = vesting_price
    else:
        plus_value = 0
        vesting_price_with_moins_value = selling_price
    rebate = compute_rebate(selling_date_dt, vesting_date_dt, macron_law_id)
    # Not excatly it, not sure how to handle rebate and deductible csg at the same time, upper bound
    tax_to_pay = vesting_price_with_moins_value * (
                (1 - rebate) * tax_info_dict['TMI_IR'] + tax_info_dict[
            'cotisation']) + plus_value * tax_info_dict[
                     'flat_tax_plus_value']
    return {'vesting_price': vesting_price,
            'vesting_price_with_moins_value': vesting_price_with_moins_value,
            'plus_value': plus_value, 'selling_price': selling_price,
            'rebate': rebate, 'tax': tax_to_pay}


############################################################################################
#########################       Matching functions
############################################################################################
# These functions decide which RSU are sold at each sell time. Income tax will differ depending on 
# the one used. I recommend the get_sale_order_from_optionality


def get_sale_order_greedy(sell_event, portfolio, tax_info_dict=tax_info_dict,
                          criteo_stock_dict=criteo_stock_dict,
                          exchange_rate_dict=exchange_rate_dict):
    sale_tax_info = []
    for i, event in enumerate(portfolio['available_stock']):
        tax_info = compute_tax_info_from_matched_transaction(sell_event['date'],
                                                             event['date'],
                                                             sell_event[
                                                                 'stock_unit_price_USD'],
                                                             macron_law_id=
                                                             event[
                                                                 'macron_law_id'],
                                                             tax_info_dict=tax_info_dict,
                                                             criteo_stock_dict=criteo_stock_dict,
                                                             exchange_rate_dict=exchange_rate_dict)
        sale_tax_info.append({'position': i, 'available_stock': event['amount'],
                              'tax': tax_info['tax']})

    ordered_sale = sorted(sale_tax_info, key=lambda k: k['tax'])

    remaining_share_to_sell = sell_event['amount']
    sale_order = []
    for sale in ordered_sale:
        sale_position = sale['position']
        share_sold = min(portfolio['available_stock'][sale_position]['amount'],
                         remaining_share_to_sell)
        remaining_share_to_sell = remaining_share_to_sell - share_sold
        sale_order.append({'position': sale_position, 'share_sold': share_sold})
        if remaining_share_to_sell == 0:
            return sale_order

    return 'error, you did not have enough share to sell this amount, please check'


def get_sale_order_from_optionality(sell_event, portfolio,
                                    tax_info_dict=tax_info_dict,
                                    criteo_stock_dict=criteo_stock_dict,
                                    exchange_rate_dict=exchange_rate_dict):
    # The change of tax rate at the vesting price means our RSU are not a forward with regards to the 
    # criteo stock, but a forward + a call option without time limit. It means that it is more interesting to
    # sell the shares whose current price are the farthest from the vesting price, as their optionality is
    # less valuable than those whose vesting price are close to current price.
    # This version is not the most optimal, but I don't know how to get the optimal without brute force 
    # and I am too lazy to code the brute force.
    # This version might lead you to pay more tax on your RSU this year than you could, but if you believe finance 
    # theories, it should be close to the optimal (meaning you should pay less next year and over the two years)
    # I am priorizing stock with rebate to be sold first, and then I take the opportunity the furthest from the stock price
    sale_tax_info = []
    selling_price = get_stock_price_euro_from_price_in_USD(sell_event['date'],
                                                           sell_event[
                                                               'stock_unit_price_USD'])

    for i, event in enumerate(portfolio['available_stock']):
        tax_info = compute_tax_info_from_matched_transaction(sell_event['date'],
                                                             event['date'],
                                                             sell_event[
                                                               'stock_unit_price_USD'],
                                                             macron_law_id=
                                                             event[
                                                                 'macron_law_id'],
                                                             tax_info_dict=tax_info_dict,
                                                             criteo_stock_dict=criteo_stock_dict,
                                                             exchange_rate_dict=exchange_rate_dict)
        score_for_sorting = -np.abs(np.log(selling_price / tax_info[
            'vesting_price'])) - 100 * (tax_info['rebate'] > 0) -1000 * event.get('amount_already_declared',0)
        sale_tax_info.append({'position': i, 'available_stock': event['amount'],
                              'tax': tax_info['tax'],
                              'score_for_sorting': score_for_sorting})

    ordered_sale = sorted(sale_tax_info, key=lambda k: k['score_for_sorting'])

    remaining_share_to_sell = sell_event['amount']
    sale_order = []
    for sale in ordered_sale:
        sale_position = sale['position']
        share_sold = min(portfolio['available_stock'][sale_position]['amount'],
                         remaining_share_to_sell)
        remaining_share_to_sell = remaining_share_to_sell - share_sold
        sale_order.append({'position': sale_position, 'share_sold': share_sold})
        if remaining_share_to_sell == 0:
            return sale_order
    if remaining_share_to_sell > 0:
        raise Exception(
            'error, you did not have enough share to sell this amount, please check')


def get_sale_order_fifo(sell_event, portfolio, tax_info_dict=tax_info_dict,
                        criteo_stock_dict=criteo_stock_dict,
                        exchange_rate_dict=exchange_rate_dict):
    # at each sale, sell the first vested stock 

    remaining_share_to_sell = sell_event['amount']
    sale_order = []
    for i, sale in enumerate(portfolio['available_stock']):
        sale_position = i
        share_sold = min(portfolio['available_stock'][sale_position]['amount'],
                         remaining_share_to_sell)
        remaining_share_to_sell = remaining_share_to_sell - share_sold
        sale_order.append({'position': sale_position, 'share_sold': share_sold})
        if remaining_share_to_sell == 0:
            return sale_order
    if remaining_share_to_sell > 0:
        raise Exception(
            'error, you did not have enough share to sell this amount, please check')


###################################################################################################
#         Main function, for each sales computes important information
###################################################################################################
def get_sales_result(sell_event, portfolio,
                     matching_method=get_sale_order_from_optionality,
                     tax_info_dict=tax_info_dict,
                     criteo_stock_dict=criteo_stock_dict,
                     exchange_rate_dict=exchange_rate_dict):
    sale_order = matching_method(sell_event, portfolio,
                                 tax_info_dict=tax_info_dict,
                                 criteo_stock_dict=criteo_stock_dict,
                                 exchange_rate_dict=exchange_rate_dict)
    sale_recap = []
    nb_sales = len(sale_order)
    for vested_action_sale in sale_order:
        vested_event = portfolio['available_stock'][
            vested_action_sale['position']]
        tax_info = compute_tax_info_from_matched_transaction(sell_event['date'],
                                                             vested_event[
                                                                 'date'],
                                                             sell_event[
                                                                 'stock_unit_price_USD'],
                                                             macron_law_id=
                                                             vested_event[
                                                                 'macron_law_id'],
                                                             tax_info_dict=tax_info_dict,
                                                             criteo_stock_dict=criteo_stock_dict,
                                                             exchange_rate_dict=exchange_rate_dict)
        montant_global_516 = tax_info['selling_price'] * vested_action_sale[
            'share_sold']
        # frais separer egalement sur les differentes transactions
        frais_de_cession_517 = sell_event[
                                   'total_fee_dollars'] / get_value_on_date(
            sell_event['date'], exchange_rate_dict) / nb_sales
        prix_de_cession_net_518 = montant_global_516 - frais_de_cession_517
        prix_daquisition_global = tax_info['vesting_price'] * \
                                  vested_action_sale[
                                      'share_sold']
        resultat = prix_de_cession_net_518 - prix_daquisition_global
        sale_recap.append({
            'date de la cession (513)': sell_event['date'],
            'valeur unitaire de la cession (514)': tax_info['selling_price'],
            'nombre de titres cedes (515)': vested_action_sale['share_sold'],
            'montant global (516)': montant_global_516,
            'frais de cession (517)': frais_de_cession_517,
            'prix de cession net (518)': prix_de_cession_net_518,
            'prix ou valeur acquisition unitaire (520)': tax_info[
                'vesting_price'],
            'prix daquisition global (521 et 523)': prix_daquisition_global,
            'resultat': resultat,
            'vesting_amount_with_moins_value': vested_action_sale[
                                                   'share_sold'] * tax_info[
                                                   'vesting_price_with_moins_value'],
            'rebate_with_moins_value': vested_action_sale[
                                              'share_sold'] *
                                          tax_info[
                                              'vesting_price_with_moins_value'] *
                                          tax_info['rebate'],
            'rebate': tax_info['rebate'],
            'tax': vested_action_sale['share_sold'] * tax_info['tax'],
            'macron_law_id': vested_event['macron_law_id']

        })
        portfolio['available_stock'][vested_action_sale['position']]['amount'] = \
            portfolio['available_stock'][vested_action_sale['position']][
                'amount'] - \
            vested_action_sale['share_sold']
        if portfolio['available_stock'][vested_action_sale['position']].get('amount_already_declared',0) > 0:
            portfolio['available_stock'][vested_action_sale['position']]['amount_already_declared'] = max(0, \
                  portfolio['available_stock'][vested_action_sale['position']]['amount_already_declared'] - \
            vested_action_sale['share_sold'])
    available_stock_after_transaction = []
    for available_stock in portfolio['available_stock']:
        if available_stock['amount'] > 0:
            available_stock_after_transaction.append(available_stock)
    return available_stock_after_transaction, sale_recap
