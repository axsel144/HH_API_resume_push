from oauthlib.oauth2 import WebApplicationClient
import requests
import time
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException
from selenium import webdriver
from configparser import ConfigParser
import datetime
import json
from urllib.parse import urlparse, parse_qs
import math
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from colorama import Fore, init
init(autoreset=True)

with open("auth.json", "r") as f:
    credentials = json.load(f)
    LOGIN = credentials["email"]
    PASSWORD = credentials["password"]


config = ConfigParser()
config.read("config.ini")
client_id = config.get("app_auth", "client_id")
client_secret = config.get("app_auth", "client_secret")
redirect_uri = config.get("app_auth", "redirect_uri")
authorization_base_url = config.get("app_auth", "authorization_base_url")
token_url = config.get("app_auth", "token_url")
token_life = str(datetime.datetime.now())
RESUME_URL = "https://api.hh.ru/resumes/"


def init_get_token():
    client = WebApplicationClient(client_id)
    auth_token = start_browser(client)
    return auth_token


def gen_auth_url(client):
    authorization_url = client.prepare_request_uri(authorization_base_url, redirect_uri=redirect_uri)
    generation_url_time = datetime.datetime.now()
    print(generation_url_time, 'URL для авторизации сформировано:' + authorization_url)
    return authorization_url


def start_browser(client):
    options = webdriver.ChromeOptions()
    options.add_argument("--no-sandbox")
    options.add_argument("--headless=new")
    # Отправляем пользователя по URL для авторизации
    open_chrome_time: datetime = datetime.datetime.now()
    print(open_chrome_time, Fore.BLUE + 'Открываем браузер')
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    driver.get(url=str(gen_auth_url(client)))
    try:
        driver.find_element(
            by=By.XPATH, value="//input[@data-qa='login-input-username']").send_keys(LOGIN)
        driver.find_element(
            by=By.XPATH, value="//input[@data-qa='login-input-password']").send_keys(PASSWORD)
        driver.find_element(
            by=By.XPATH, value="//button[@data-qa='account-login-submit']").click()
        # time.sleep(15)
        auth_end_time = datetime.datetime.now()
        print(auth_end_time, Fore.BLUE + "Успешная авторизация")
        time.sleep(5)
        url = driver.current_url
        parsed_url = urlparse(url)
        parsed_query = parse_qs(parsed_url.query)
        auth_token = parsed_query.get('code')
        authcode = "".join(auth_token)
        auth_code_time = datetime.datetime.now()
        print(auth_code_time, 'Код авторизации: ', Fore.GREEN + authcode)
        return authcode
    except NoSuchElementException:
        auth_error_time: datetime = datetime.datetime.now()
        print(auth_error_time, Fore.RED + "Не получилось послать данные авторизации")


def convert_auth_to_token(authcode):
    set_token_expire()
    data = {
        'grant_type': 'authorization_code',
        'code': authcode,
        'client_id': client_id,
        'client_secret': client_secret,
        'redirect_uri': redirect_uri
    }
    hed = {"Content-Type": "application/x-www-form-urlencoded"}
    response2 = requests.post('https://hh.ru/oauth/token', params=data, headers=hed)
    return response2


def resume_publish(sel_resume_id):
    publish_url = RESUME_URL + sel_resume_id + '/publish'
    check_token_expire()
    hed = {"Authorization": "Bearer %s" % token}
    response = requests.post(publish_url, headers=hed)
    if response.status_code < 300:
        response_time = datetime.datetime.now()
        print(response_time, Fore.GREEN + 'Резюме было обновлено')
        return response
    elif response.status_code >= 300:
        error_time = datetime.datetime.now()
        print(error_time, Fore.RED + 'Ошибка при обновлении резюме!')
        print(Fore.RED, '[Debug] Status Code: ', response.status_code)
        print(Fore.RED, '[Debug] Response text: ', response.text)


def get_refresh_token():
    global token
    global refresh_token
    data = {
        'grant_type': 'refresh_token',
        'refresh_token': refresh_token,
    }
    hed = {"Content-Type": "application/x-www-form-urlencoded"}
    response3 = requests.post('https://hh.ru/oauth/token', params=data, headers=hed).json()
    print(response3)
    if 'error' not in response3.keys():
        token = response3["access_token"]
        refresh_token = response3["refresh_token"]
        response_time = datetime.datetime.now()
        set_token_expire()
        print(response_time, 'Токен был обновлен')
        return True
    if 'error' in response3.keys():
        error_time = datetime.datetime.now()
        print(error_time, Fore.RED + 'Ошибка при обновлении токена! Пытаемся пройти процесс авторизации')
        auth_code: str = init_get_token()
        token_str = convert_auth_to_token(auth_code).json()
        new_token = token_str["access_token"]
        token_convert_time = datetime.datetime.now()
        print(token_convert_time, 'Первичный токен получен: ', Fore.GREEN + token)
        new_refresh_token = token_str["refresh_token"]
        config["app_auth"]["token"] = new_token
        config["app_auth"]["refresh_token"] = new_refresh_token
        with open('config.ini', 'w') as conf:  # save
            config.write(conf)
        return False


def parsed_date_convert(parsed_date):
    date_time_obj = datetime.datetime.strptime(parsed_date, '%Y-%m-%dT%H:%M:%S+0300')
    date_time_obj = date_time_obj + datetime.timedelta(hours=4) + datetime.timedelta(minutes=1)
    # formated_date = str(date_time_obj)
    return date_time_obj


def get_uptime_resume(oauth_token, sel_resume_id):
    check_token_expire()
    global token
    hed = {"Authorization": "Bearer %s" % oauth_token}
    response = requests.get('https://api.hh.ru/resumes/' + sel_resume_id, headers=hed)
    if response.status_code < 300:
        parsed_response = response.json()
        uptime_parsed = parsed_response["updated_at"]
        date_time_obj = datetime.datetime.strptime(uptime_parsed, '%Y-%m-%dT%H:%M:%S+0300')
        date_time_obj = date_time_obj + datetime.timedelta(hours=4) + datetime.timedelta(minutes=1)
        log_time = datetime.datetime.now()
        print(log_time, 'Следующая попытка: ', date_time_obj)
        now_date = datetime.datetime.now()
        delta = date_time_obj - now_date
        delta_delayed: float = delta.total_seconds()
        return delta_delayed
    if response.status_code >= 300:
        log_time = datetime.datetime.now()
        print(log_time, Fore.BLUE + 'Предполагаю, что токен просрочился. Пробуем его освежить')
        token = get_refresh_token()
        return False


def set_token_expire():
    token_expire_date = datetime.datetime.now() + datetime.timedelta(days=14) + datetime.timedelta(minutes=20)
    config["app_auth"]["token_expire_date"] = str(token_expire_date)
    with open('config.ini', 'w') as conf:  # save
        config.write(conf)
# return token_expire_date
    return True


def check_token_expire():
    global token, refresh_token
    config.read("config.ini")
    token = config.get("app_auth", "token")
    refresh_token = config.get("app_auth", "refresh_token")
    current_datetime = datetime.datetime.now()
    token_expire_raw = config.get("app_auth", "token_expire_date")
    token_expire_date = datetime.datetime.strptime(token_expire_raw, '%Y-%m-%d %H:%M:%S.%f')
    if token_expire_date > current_datetime:
        print(current_datetime, Fore.GREEN + 'Токен живой и будет жить до :', token_expire_date)
        return True
    else:
        print(current_datetime, Fore.RED + 'Токен просрочился, пытаемся его освежить ')
        get_refresh_token()
        return False


def get_oldest_resume_id(oauth_token):
    hed = {"Authorization": "Bearer %s" % oauth_token}
    response = requests.get('https://api.hh.ru/resumes/mine', headers=hed)
    if response.status_code < 300:
        test_parse = response.json()
        updates = [a['updated_at'] for a in test_parse['items'] if 'updated_at' in a]
        updates_conv = list(map(parsed_date_convert, updates))
        ids = [d['id'] for d in test_parse['items'] if 'id' in d]
        # names = [c['last_name'] for c in test_parse['items'] if 'last_name' in c]
        count = len(ids)
        # print('Доступных резюме:',  count)
        list_merged = []
        for i in range(count):
            list_merged.append(updates_conv[i])
            list_merged.append(ids[i])
            # list_merged.append(names[i])
            i += 1
        # print(list_merged)
        for p in range(count):
            if list_merged[p] > list_merged[p + 2]:
                print('Планируем пинать резюме с', list_merged[p + 3], '', list_merged[p + 2])
                return list_merged[p + 3], list_merged[p + 2]
            if list_merged[p] < list_merged[p + 2]:
                print('Планируем пинать резюме с', list_merged[p + 1], '', list_merged[p])
                return list_merged[p + 1], list_merged[p]
            else:
                print('Ошибка!')
                break


if __name__ == "__main__":
    config.read("config.ini")
    token = config.get("app_auth", "token")
    refresh_token = config.get("app_auth", "refresh_token")
    # resume_id = get_resume_list(token)
    while True:
        config.read("config.ini")
        token = config.get("app_auth", "token")
        refresh_token = config.get("app_auth", "refresh_token")
        # uptime = get_uptime_resume(token, resume_id)
        resume: tuple = get_oldest_resume_id(token)
        resume_id = resume[0]
        uptime = get_uptime_resume(token, resume_id)

        if uptime > 0:
            logtime = datetime.datetime.now()
            print(logtime, '[Debug] uptime more than zero', uptime)
            uptime_log = datetime.datetime.now()
            uptime_minutes = (int(uptime) / 60) + 5
            uptime_minutes = math.ceil(uptime_minutes)
            print(uptime_log, 'Резюме свежее, обновление через ', Fore.GREEN + str(uptime_minutes),  ' минут')
            time.sleep(int(uptime))
            continue

        if uptime <= 0:
            logtime = datetime.datetime.now()
            print(logtime, '[Debug] uptime less than zero: ', uptime)
            uptime_log = datetime.datetime.now()
            print(uptime_log, Fore.GREEN + 'Настало время пнуть резюме')
            resume_publish(resume_id)
            uptime = 1
            continue
        else:
            uptime_log = datetime.datetime.now()
            print(uptime_log, Fore.RED + '[CRITICAL Error] - что-то не так с uptime: ', uptime)
            break
            # print(uptime_log, 'Скорее всего просрочился токен, освежаем:')
            # token = get_refresh_token(token)
