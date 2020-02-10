import telegram
from telegram.ext import Updater, MessageHandler, Filters, CommandHandler
import logging
import geopandas as gpd
import pandas as pd
from shapely.geometry import Point, Polygon
import os
from matplotlib.ticker import MaxNLocator
import matplotlib.pyplot as plt
import random

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                     level=logging.INFO)


class CrimenCDMX:
    
    def __init__(self):
        colonias = gpd.read_file('data/colonias-shp.shp')
        self.colonias = colonias[~pd.isnull(colonias['geometry'])]
    
        crimen = pd.read_csv('data/carpetas-de-investigacion-pgj-de-la-ciudad-de-mexico (1).csv')
        dic_crimenes = crimen[(crimen['mes_hechos'] == 'Diciembre') & (crimen['ao_hechos']==2019)]
        self.dic_crimenes = dic_crimenes[~pd.isna(dic_crimenes['colonia_hechos'])]


    def get_colonia(self, point):
        filt_col = [point.within(row['geometry']) for idx, row in self.colonias.iterrows()]
        df = self.colonias[filt_col]

        if len(df) == 0:
            return 'No encontré colonias'
        else:
            return df.iloc[0]['COLONIA'], df.iloc[0]['geometry']
        
    def get_plot(self, df, col):
        df_r = ( 
            df.assign(fecha_hechos = lambda x: pd.to_datetime(x['fecha_hechos']).dt.date)
              .groupby(['fecha_hechos', 'categoria_delito'])
              .size()
              .reset_index(name='n')
              .set_index(['fecha_hechos', 'categoria_delito']).unstack(fill_value=0).reset_index()
        )

        df_r.columns = df_r.columns.droplevel()
        df_r.rename(columns={'': 'fecha'}, inplace=True)

        df_fechas = pd.DataFrame({'fecha': pd.date_range('2019-12-01', '2019-12-31')})
        df_r = df_fechas.merge(df_r, how='left', on=['fecha']).fillna(0)

        temp_file = random.randint(1, 1000000)
        name_temp_file = f'temp_{temp_file}.png'

        ax = df_r.set_index('fecha').plot()
        ax.yaxis.set_major_locator(MaxNLocator(integer=True))
        ax.legend(bbox_to_anchor=(0., 1.02, 1., .102), loc='lower left',
                   ncol=1, mode="expand", borderaxespad=0.)
        ax.set_ylabel('Incidencia delictivas\nDiciembre 2019')
        ax.set_xlabel(f'COLONIA: {col}')
        plt.tight_layout()
        plt.savefig(name_temp_file)
        plt.close()


        return name_temp_file 

    def get_crimes(self, point):

        col, geo = self.get_colonia(point)

        filt_crimes = [Point(row['latitud'], row['longitud']).within(geo) for idx, row in self.dic_crimenes.iterrows()]

        crimes = self.dic_crimenes[filt_crimes]
        

        if len(crimes) == 0:
            response = 'No crímenes reportados en diciembre\n'
            response += 'Estás fuera de la CDMX?'
            return response
        else:
            name_temp_file = self.get_plot(crimes, col)
            crimes = crimes.groupby(['delito']).size().reset_index(name='n')
            response = 'Para *diciembre de 2019*\n'
            response += 'he podido detectar lo siguiente:\n\n'
            response += f'Colonia: *{col}* \n\n'
            for idx, row in crimes.iterrows():
                response+= row['delito'] + ': ' + '*'+ str(row['n']) + '*'+'\n'
            return response, name_temp_file

def start(update, context):
    location_keyboard = telegram.KeyboardButton(text="Mandar ubicación", request_location=True)
    #contact_keyboard = telegram.KeyboardButton(text="send_contact", request_contact=True)
    custom_keyboard = [[location_keyboard]]
    reply_markup = telegram.ReplyKeyboardMarkup(custom_keyboard)
    context.bot.send_message(
        chat_id=update.effective_chat.id, 
        text="Soy un bot de crimen, mándame tu ubicación!", 
        reply_markup=reply_markup
    )


def response_location(update, context, CrimenCDMX):
    latitude = update.effective_message.location.latitude
    longitude = update.effective_message.location.longitude
    point = Point(latitude, longitude)
    response = CrimenCDMX.get_crimes(point)
    if type(response) is tuple:
        context.bot.send_message(chat_id=update.effective_chat.id, text=response[0], parse_mode=telegram.ParseMode.MARKDOWN)
        context.bot.send_photo(chat_id=update.effective_chat.id, photo=open(response[1], 'rb'))
    else:
        context.bot.send_message(chat_id=update.effective_chat.id, text=response, parse_mode=telegram.ParseMode.MARKDOWN)
    
def unknown(update, context):
    context.bot.send_message(chat_id=update.effective_chat.id, text="Lo siento, solo puedo ayudarte si me mandas tu ubicación geográfica.")
    
def main():
   
    
    token = os.environ['TOKEN_CRIME_BOT']
    updater = Updater(token=token, use_context=True)
    dispatcher = updater.dispatcher
    
    start_handler = CommandHandler('start', start)
    dispatcher.add_handler(start_handler)
    
    crimenCDMX = CrimenCDMX()
    
    response_loc_wrapper = lambda update, context: response_location(update, context, crimenCDMX)
    
    location_handler = MessageHandler(Filters.location, response_loc_wrapper)
    dispatcher.add_handler(location_handler)
    
    unknown_handler = MessageHandler(~Filters.location, unknown)
    dispatcher.add_handler(unknown_handler)
    
    updater.start_polling()
    
    updater.idle()
    
if __name__ == '__main__':
    main()
    

