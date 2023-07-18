import datetime
import json
import math
import time
from configparser import ConfigParser
from urllib.parse import urlparse, parse_qs
import requests
from colorama import Fore, init
from oauthlib.oauth2 import WebApplicationClient
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager

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


def start_browser():
    client = WebApplicationClient(client_id)
    options = webdriver.ChromeOptions()
    options.add_argument("--no-sandbox")
    options.add_argument("--headless=new")
    open_chrome_time: datetime = datetime.datetime.now()
    print(open_chrome_time, Fore.BLUE + 'Открываем браузер')
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    authorization_url = str(client.prepare_request_uri(authorization_base_url, redirect_uri=redirect_uri))
    generation_url_time = datetime.datetime.now()
    print(generation_url_time, 'URL для авторизации сформировано:' + authorization_url)
    driver.get(url=authorization_url)
    try:
        driver.find_element(
            by=By.XPATH, value="//input[@data-qa='login-input-username']").send_keys(LOGIN)
        driver.find_element(
            by=By.XPATH, value="//input[@data-qa='login-input-password']").send_keys(PASSWORD)
        driver.find_element(
            by=By.XPATH, value="//button[@data-qa='account-login-submit']").click()
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
    data = {
        'grant_type': 'authorization_code',
        'code': authcode,
        'client_id': client_id,
        'client_secret': client_secret,
        'redirect_uri': redirect_uri
    }
    hed = {"Content-Type": "application/x-www-form-urlencoded"}
    response2 = requests.post('https://hh.ru/oauth/token', params=data, headers=hed)
    print('Debug - convert_auth_to_token status_code: ', response2.status_code)
    print('Debug - check text: ', response2.text)
    token_conv_raw = response2.json()
    token_new = token_conv_raw["access_token"]
    refresh_token_new = token_conv_raw["refresh_token"]
    write_to_conf("app_auth", "token", token_new)
    write_to_conf("app_auth", "refresh_token", refresh_token_new)
    return response2


def resume_publish(sel_resume_id):
    publish_url = RESUME_URL + sel_resume_id + '/publish'
    check_token_expire()
    hed = {"Authorization": "Bearer %s" % token}
    print('[Debug] - resume_publish status code:', requests.post(publish_url, headers=hed).status_code)


def get_refresh_token():
    config.read("config.ini")
    refresh_token_old = config.get("app_auth", "refresh_token")
    data = {
        'grant_type': 'refresh_token',
        'refresh_token': refresh_token_old,
    }
    hed = {"Content-Type": "application/x-www-form-urlencoded"}
    response3 = requests.post('https://hh.ru/oauth/token', params=data, headers=hed)
    status = response3.ok
    text = response3.text
    response3 = response3.json()
    print('[Debug] - get_refresh_token status-code 1:', status)
    print('[Debug] Response text: ', response3)
    if 'error' not in response3.keys():
        token_new = response3["access_token"]
        refresh_token_new = response3["refresh_token"]
        response_time = datetime.datetime.now()
        set_token_expire()
        write_to_conf("app_auth", "token", token_new)
        write_to_conf("app_auth", "refresh_token", refresh_token_new)
        print(response_time, Fore.GREEN + '[INFO] Токен был обновлен')
        return True
    if status == 0:
        error_time = datetime.datetime.now()
        print(error_time, Fore.RED + '[ERROR] Ошибка при обновлении токена! Пытаемся пройти процесс авторизации')
        print(Fore.RED, '[Debug] - get_refresh_token status-code 2: ', status)
        print(Fore.RED, '[Debug] Response text: ', response3)
        auth_code: str = start_browser()
        token_str = convert_auth_to_token(auth_code).json()
        token_new = token_str["access_token"]
        token_convert_time = datetime.datetime.now()
        print(token_convert_time, '[INFO] Первичный токен получен: ', Fore.GREEN + token)
        refresh_token_new = token_str["refresh_token"]
        write_to_conf("app_auth", "token", token_new)
        write_to_conf("app_auth", "refresh_token", refresh_token_new)
    if 'token not expired' in text:
        print('Токен еще живой')
        set_token_expire()
        return True


def write_to_conf(group, key, value):
    config[str(group)][str(key)] = str(value)
    with open('config.ini', 'w') as conf:
        config.write(conf)


def parsed_date_convert(parsed_date):
    date_time_obj = datetime.datetime.strptime(parsed_date, '%Y-%m-%dT%H:%M:%S+0300')
    date_time_obj = date_time_obj + datetime.timedelta(hours=4) + datetime.timedelta(minutes=1)
    return date_time_obj


def get_uptime_resume(sel_resume_id):
    check_token_expire()
    config.read("config.ini")
    oauth_token = config.get("app_auth", "token")
    hed = {"Authorization": "Bearer %s" % oauth_token}
    response = requests.get('https://api.hh.ru/resumes/' + sel_resume_id, headers=hed)
    if response.status_code < 300:
        parsed_response = response.json()
        resume_uptime = parsed_date_convert(parsed_response["updated_at"])
        now_date = datetime.datetime.now()
        delta = resume_uptime - now_date
        delta_delayed: float = delta.total_seconds()
        return delta_delayed
    elif response.status_code > 300:
        err_time = datetime.datetime.now()
        print(err_time, '[ERROR] Something wrong with getting resume uptime!')
        print('[Debug] - get_uptime_resume Status code:', response.status_code)
        print('[Debug] Resolve:', response.text)
        return 1


def set_token_expire():
    loger_time = datetime.datetime.now()
    token_expire_date = str(datetime.datetime.now() + datetime.timedelta(days=14) + datetime.timedelta(minutes=20))
    write_to_conf("app_auth", "token_expire_date", token_expire_date)
    print(loger_time, 'Дата окончания токена была успешно записана')


def check_token_expire():
    config.read("config.ini")
    token_chk = config.get("app_auth", "token")
    hed = {"Authorization": "Bearer %s" % token_chk}
    response = requests.get('https://api.hh.ru/resumes/mine', headers=hed)
    status_chk = response.status_code
    current_datetime = datetime.datetime.now()
    if status_chk < 300:
        token_expire_raw = config.get("app_auth", "token_expire_date")
        token_expire_date = datetime.datetime.strptime(token_expire_raw, '%Y-%m-%d %H:%M:%S.%f')
        # if token_expire_date > current_datetime:
        #     print(current_datetime, '[INFO] Токен живой и будет жить до :', Fore.YELLOW + str(token_expire_date))
    if status_chk == 403:
        print('[Debug] - check_token_expire status 1: ', status_chk)
        print('Debug - check text: ', response.text)
        print(current_datetime, Fore.BLUE + '[INFO] Токен просрочился, пытаемся его освежить через API ')
        get_refresh_token()

    # if status_chk > 400:
    #     token_update_time = datetime.datetime.now()
    #     print('[Debug] - check_token_expire status 2', status_chk)
    #     print('Debug - check text: ', response.text)
    #     print(token_update_time, Fore.RED + '[WARN] - Все же токен сильно просрочился, освежаем его через Chrome')
    #     token_str = convert_auth_to_token(start_browser()).json()
    #     token_chk = token_str["access_token"]
    #     write_to_conf("app_auth", "token", token_chk)


def get_oldest_resume_id():
    check_token_expire()
    config.read("config.ini")
    o_token = config.get("app_auth", "token")
    hed = {"Authorization": "Bearer %s" % o_token}
    response = requests.get('https://api.hh.ru/resumes/mine', headers=hed)
    test_parse = response.json()
    updates = [a['updated_at'] for a in test_parse['items'] if 'updated_at' in a]
    updates_conv = list(map(parsed_date_convert, updates))
    ids = [d['id'] for d in test_parse['items'] if 'id' in d]
    count = len(ids)
    list_merged = []
    for i in range(count):
        list_merged.append(updates_conv[i])
        list_merged.append(ids[i])
        i += 1
    for p in range(count):
        current_datetime = datetime.datetime.now()
        if list_merged[p] > list_merged[p + 2]:
            print(current_datetime, '[INFO] Планируем пинать резюме с id ' + Fore.GREEN + str(list_merged[p + 3]), 'в'
                                        , Fore.CYAN + str(list_merged[p + 2]))
            return list_merged[p + 3], list_merged[p + 2]
        if list_merged[p] < list_merged[p + 2]:
            print(current_datetime, '[INFO] Планируем пинать резюме с id'
                                        , Fore.GREEN + str(list_merged[p + 1]), 'в', Fore.CYAN + str(list_merged[p]))
            return list_merged[p + 1], list_merged[p]
        else:
            print(current_datetime, Fore.RED + '[ERROR] Ошибка! Проблема в оперделении старшего резюме')
            break


if __name__ == "__main__":
    while True:
        config.read("config.ini")
        token = config.get("app_auth", "token")
        refresh_token = config.get("app_auth", "refresh_token")
        resume = list(get_oldest_resume_id())
        resume_id = resume[0]
        uptime = get_uptime_resume(resume_id)
        if uptime > 0:
            logtime = datetime.datetime.now()
            uptime_log = datetime.datetime.now()
            uptime_minutes = (int(uptime) / 60) + 5
            uptime_minutes = math.ceil(uptime_minutes)
            print(uptime_log, '[INFO] Резюме свежее, обновление через ', Fore.GREEN + str(uptime_minutes),  ' минут')
            time.sleep(int(uptime))
            continue
        elif uptime <= 0:
            logtime = datetime.datetime.now()
            uptime_log = datetime.datetime.now()
            print(uptime_log, '[INFO] Настало время пнуть резюме')
            resume_publish(resume_id)
            uptime = 1
            continue
        else:
            uptime_log = datetime.datetime.now()
            print(uptime_log, Fore.RED + '[CRITICAL Error] - что-то не так с uptime: ', uptime)
            break
