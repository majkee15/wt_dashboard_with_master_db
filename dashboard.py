import dash
import dash_core_components as dcc
import dash_html_components as html
import dash_bootstrap_components as dbc
import dash_table as dtt
from dash.dependencies import Input, Output
import plotly.graph_objs as go
import numpy as np
import pandas as pd

import riskparity
import outils
from data_fetcher import DataFetcher

from datetime import datetime, timedelta
import os

# TODO implement local serving of the css file
today = datetime.today()

db_file = 'stock_prices_eod.sqlite3'
data_path = os.path.join(db_file)
print(os.getcwd())
fetcher = DataFetcher(data_path)
rp_portfolio = [{'label': stock, 'value': stock} for stock in fetcher.tickers]

external_stylesheets = ['https://codepen.io/trooperandz/pen/YRpKjo.css']
# external_stylesheets = ['https://codepen.io/chriddyp/pen/bWLwgP.css']
app = dash.Dash(__name__, external_stylesheets=external_stylesheets)

app.layout = html.Div(className='grid-container', children=[
    html.Div(className='menu-icon', children=[
        html.I(className="fas fa-bars header__menu", children='SC')
    ]),
    html.Header(className='header', children=[
        html.Div(className="header__search", children=
        dcc.Dropdown(id='universe', options=rp_portfolio, value=outils.rp_all_weather,
                     multi=True,
                     placeholder='Select the universe....and life duh', loading_state={},
                     style={'width': 'auto', 'color': 'black'}
                     )),
        html.Div(className='header__avatar', children='Trivet & Walker Rulezzzzz'),
    ]),

    html.Aside(className='sidenav', children=[
        html.Div(className='sidenav__close-icon'),
        html.I(className="fas fa-times sidenav__brand-close"),
        html.Ul(className="sidenav__list", children=[
            html.Li(className="sidenav__list-item", children='All Weather', id='AW'),
            html.Li(className="sidenav__list-item", children='AR Cowboy', id='ARC'),
            html.Li(className="sidenav__list-item", children='AR Nerd', id='ARN'),
            # html.Li(className="sidenav__list-item", children='Rocket')
        ])
    ]),
    html.Main(className='main', children=[
        html.Div(className='"main-header"', children=[
            html.Div(
                dcc.Graph(
                    figure=go.Figure(
                        data=[],
                        layout=go.Layout(
                            title='Universe - Historical Price Data',
                        )
                    ),
                    id='graph-prices'
                )
            ),
            html.H5("Momentum lookback:", style={'width': 'auto', 'display': 'inline-block'}),
            html.Div(dcc.Input(id='mom-lookback', value=110, type='number'),
                     style={'width': 'auto', 'display': 'inline-block'}),
            html.H5("Volatility lookback:", style={'width': 'auto', 'display': 'inline-block'}),
            html.Div(dcc.Input(id='vol-lookback', value=21, type='number'),
                     style={'width': 'auto', 'display': 'inline-block'}),
            html.Div(children=[
                dcc.Graph(figure=go.Figure(
                    data=[],
                    layout=go.Layout(
                        title='Momentum History',
                    )
                ),
                    id='graph-mom')
            ]),
            html.Div(children=[
                dcc.Graph(figure=go.Figure(
                    data=[],
                    layout=go.Layout(
                        title='Volatility History',
                    )
                ),
                    id='graph-vol')
            ]),
        ]),
        html.Div(className="main-header__heading", children=[
            html.H5('Number of assets held:', style={'width': 'auto', 'display': 'inline-block'}),
            dcc.Input(id='k', value=4, type='number', style={'width': 'auto', 'display': 'inline-block'}),
            html.H5('Rebalance history:', style={'width': 'auto', 'display': 'inline-block'})
                 ]),
        html.Div(
            dtt.DataTable(id='table-results', columns = [{"name": i, "id": i} for i in []], data=[{}])
            ,style={'color': 'black'}
        )

    ])
])


# Graph prices REACT
@app.callback(Output('graph-prices', 'figure'), [Input('universe', 'value')])
def update_figure(assets):
    df = fetcher.fetch_price_data(assets, date_from=today - timedelta(days=365 * 2))
    traces = [go.Scatter(x=df.index.to_series(),
                         y=df[stock], mode='lines', name=stock) for stock in assets]
    return {
        'data': traces,
        'layout': go.Layout(title='Universe Historical Data')
    }


# Graph momentum REACT
@app.callback(
    Output('graph-mom', 'figure'),
    [Input('mom-lookback', 'value'), Input('universe', 'value')])
def update_figure(lookback, assets):
    df = fetcher.fetch_price_data(assets, date_from=today - timedelta(days=365 * 2))
    traces = [go.Scatter(x=df.index.to_series(),
                         y=df[stock].rolling(lookback).apply(lambda x: (x[-1]) / x[0], raw=True), mode='lines',
                         name=stock) for stock in assets]
    return {
        'data': traces,
        'layout': go.Layout(title='Momentum History')
    }

# k - number of assets safeguard
@app.callback(Output('k', 'value'), [Input('universe', 'value')])
def check_k(universe):
    k = 4
    if len(universe) < k:
        k = len(universe)
    return k


# Graph volatility REACT
@app.callback(
    Output('graph-vol', 'figure'),
    [Input('vol-lookback', 'value'), Input('universe', 'value')])
def update_figure(lookback, assets):
    df = fetcher.fetch_price_data(assets, date_from=today - timedelta(days=365 * 2))
    traces = [go.Scatter(x=df.index.to_series(),
                         y=df[stock].pct_change().rolling(lookback).apply(lambda x: x.std(), raw=True), mode='lines',
                         name=stock) for stock in assets]
    return {
        'data': traces,
        'layout': go.Layout(title='Returns Volatility History')
    }

# Calculate Weights React
@app.callback(
    [Output('table-results', 'data'), Output('table-results', 'columns')],
    [Input('k', 'value'), Input('mom-lookback', 'value'), Input('vol-lookback', 'value'), Input('universe', 'value')])
def update_columns(k, window_mom, window_vol, universe):
    trading_day = today
    df = fetcher.fetch_price_data(universe, date_from=today - timedelta(days=365 * 2))
    moms = df.rolling(window_mom).apply(lambda x: (x[-1]) / x[0], raw=True)
    assets_risk_budget = [1 / k] * k
    x0 = 1.0 * np.ones(k) / k
    bestmom = (moms.iloc[-1]).nlargest(k).index.values
    cov_mat = df[bestmom].pct_change().iloc[-window_vol:-1].cov()
    w = riskparity.design_pf(cov_mat.values, assets_risk_budget, x0)
    cols = [{"name": i, "id": i} for i in list(bestmom)]
    rdf = pd.DataFrame(np.array([w]),columns=bestmom)
    rows = rdf.to_dict('rows')
    return rows, cols

# #Change portfolio based on the sidebar
# @app.callback(Output("universe", "value"),[Input('AW', 'n_clicks')])
# def sidebar_AW(n_clicks):
#     return outils.rp_all_weather


@app.callback(Output("universe", "value"),[Input('AW', 'n_clicks_timestamp') ,Input('ARC', 'n_clicks_timestamp') ,Input('ARN', 'n_clicks_timestamp')])
def sidebar_AW(aw_t, arc_t, arn_t):
    ar = np.array([aw_t,arc_t,arn_t],dtype=np.float)
    switcher = {0: outils.rp_all_weather, 1: outils.american_rocket, 2:outils.new_balanced}
    if np.all(np.isnan(ar)):
        return outils.rp_all_weather
    else:
        last_clicked = np.nanargmax(ar)
        # print(f'last_clicked: {last_clicked}')
        return switcher.get(last_clicked, outils.rp_all_weather)

if __name__ == '__main__':
    app.run_server(host='0.0.0.0', debug=False, port=8050)
