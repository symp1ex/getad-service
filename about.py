import os
import sys

version = "2.1.1.7"

'''
в зависимости от того, как запускается служба, нужно менять переменную current_path

#отладочный путь под .py-скрипт
current_path = os.path.dirname(os.path.abspath(__file__))

#путь под собранный .exe-файл
current_path = os.path.dirname(sys.executable)
'''

#отладочный путь под .py-скрипт
current_path = os.path.dirname(os.path.abspath(__file__))