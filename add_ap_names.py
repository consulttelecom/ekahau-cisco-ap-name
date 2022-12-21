import shutil
import zipfile
import json
import os
import logging
import sys

__author__ = "Roman Podoynitsyn"

def mac_changer(mac):
    #This function changes MAC address format from 9800 to old ('084f.a91d.2a00'->'08:4f:a9:1d:2a:00')
    mac_new = mac.replace('.','')
    for index in [2,5,8,11,14]:
        mac_new = mac_new[:index] + ':' + mac_new[index:]
    return mac_new

def exctract_bssid(wlc_config_filename):
    # This function should extract the BSSIDs and AP names data from Cisco WLC config file (irrelevant of platform)
    bssids_dict = {}
    print('Called the function to extract BSSIDs from config file '+wlc_config_filename)
    config_strings_list, platform = file_to_string(wlc_config_filename)
    if platform == 'AireOS':
        for line in config_strings_list:
            if 'Cisco AP Name..' in line:
                ap_name = extract_value_aireos(line)
            if 'BSSID ......' in line:
                bssid = extract_value_aireos(line)
                if ap_name not in bssids_dict:
                    bssids_dict[ap_name] = bssid
    elif platform == '9800':
        ap_config_strings_list = get_config_part(config_strings_list, '--- show ap config slots ---', '--- show ap image ---')
        for line in ap_config_strings_list:
            if 'Cisco AP Name' in line:
                ap_name = line.split(':')[1].strip()
            if 'BSSID' in line:
                bssid = line.split(':')[1].strip()
                if ap_name not in bssids_dict:
                    bssids_dict[ap_name] = mac_changer(bssid)
    else:
        print('WLC platform is not found in file, make sure that you used the correct file and filename')
    logging.debug('The WLC config file is parsed, the number of BSSID-AP name pairs is ' + str(len(bssids_dict)))
    print(('The WLC config file is parsed, the number of BSSID-AP name pairs is ' + str(len(bssids_dict))))
    return bssids_dict

def get_config_part(config, start_word, stop_word):
    #This function cuts the part of config file between start word and stop word
    logging.debug('getting config section for ' + start_word + stop_word)
    config_section = []
    within_section_flag = 0
    for line in config:
        if start_word in line:
            config_section.append(line)
            within_section_flag = 1
        if within_section_flag == 1:
            config_section.append(line)
        if stop_word in line and within_section_flag == 1:
            config_section.pop()  # remove last string
            return config_section
        if stop_word in line and within_section_flag == 0:
            logging.debug('ERROR : Stop word before start word' + stop_word + start_word)
            return []
    return config_section

def extract_value_aireos(line_str):
    #This function gets rid of all points between argument and value in AireOS WLC config and returns value
    point_splitted_line = line_str.split('..')
    if point_splitted_line[-1].startswith('.'):
        point_splitted_line = point_splitted_line[-1].split('. ')
    value = point_splitted_line[-1].strip()
    return value

def file_to_string(filename):
    #This function normalizes the data from WLC config file
    print('Try to open file with name '+filename)
    config_string = []
    try:
        f = open(filename, 'r', encoding="utf8", errors='ignore')
        previous_line = ''
        for line in f:
            line_str = line.rstrip()
            if len(line_str) > 5:  # Remove empty strings
                if 'More or (q)uit' in line_str:
                    pass
                elif line.startswith('.'): #Line break in between points (bad session log from Cu)
                    config_string.pop()
                    config_string.append(previous_line+line_str)
                elif '....' in line and not '....' in previous_line and (len(line) - len(line.lstrip())) < previous_leading_spaces:#Line break in keyword
                    config_string.append(previous_line + line_str)
                else:
                    config_string.append(line_str)
            previous_line = line_str
            previous_leading_spaces = len(line) - len(line.lstrip())
        #Find platform by specific config lines
        for line in config_string:
            if 'Cisco IOS XE Software' in line:
                platform = '9800'
                break
            if 'System Inventory' in line:
                platform = 'AireOS'
                break
        logging.debug('Number of NON-EMPTY lines in config file ' + str(filename) + str(len(config_string)))
        logging.debug('Platform is ' + platform)

        f.close()
    except:
        print('File error, please check the file name and folder are correct!')
        logging.debug('File error' + str(filename))
        return None, 'empty'
    return config_string, platform

def add_ap_names(project_filename, bssid_dict):
    if not os.path.exists('Ekahau'):
        os.makedirs('Ekahau')
    working_directory = os.getcwd()
    # Load & Unzip the Ekahau Project File
    with zipfile.ZipFile(project_filename, 'r') as myzip:
        myzip.extractall(working_directory+'\\Ekahau\\')

        # Load the accessPoints.json file into the accessPoints dictionary
        with myzip.open('accessPoints.json') as json_file:
            accessPoints = json.load(json_file)

        # Load the measuredRadios.json file into the simulatedRadios dictionary
        with myzip.open('measuredRadios.json') as json_file:
            measuredRadios = json.load(json_file)

        # Load the accessPointMeasurements.json file into the simulatedRadios dictionary
        with myzip.open('accessPointMeasurements.json') as json_file:
            accessPointMeasurements = json.load(json_file)

        for item in bssid_dict.items():
            ap_name = item[0]
            bssid = item[1][:-1] #Intentionally removed last symbol from MAC address
            for measurement in accessPointMeasurements['accessPointMeasurements']:
                if bssid in measurement['mac']: #We catch BSSID -> MAC
                    logging.debug('We catched BSSID -> MAC ' + bssid + ' ' + measurement['mac'] + ' ' + measurement['id'])
                    for measuredRadio in measuredRadios['measuredRadios']:
                        if measurement['id'] in measuredRadio['accessPointMeasurementIds']: #We catch MAC -> Mesurement ID and found Access_point_ID
                            logging.debug('We catched MAC -> Mesurement ID and found Access_point_ID' + bssid + ' ' + measurement['mac'] + ' ' + measurement['id'] + ' ' + measuredRadio['accessPointId'])
                            for ap in accessPoints['accessPoints']:
                                if ap['id'] == measuredRadio['accessPointId']:
                                    #print(bssid, measurement['mac'], measurement['id'], measuredRadio['accessPointId'],ap['id'],ap['name'])
                                    print('Changed AP name in project file ', ap['name'],' to ',ap_name)
                                    ap['name'] = ap_name

    # Write the changes into the accessPoints.json File
    with open(working_directory+'\\Ekahau\\' + 'accessPoints.json', 'w') as file:
        json.dump(accessPoints, file, indent=4)
    logging.debug('New accessPoints.json file is written')

    # Create a new version of the Ekahau Project
    new_filename = project_filename + '_modified'
    shutil.make_archive(new_filename, 'zip', working_directory+'\\Ekahau\\')
    shutil.move(new_filename + '.zip', new_filename + '.esx')
    logging.debug('New project file is ready to use, filename is ' + new_filename + '.esx')
    print('New project file is ready to use, filename is ' + new_filename + '.esx')

    # Cleaning Up
    shutil.rmtree(working_directory+'\\Ekahau\\')
    logging.debug('Working folder is cleaned')

def main():
    home = os.getcwd()
    logging.basicConfig(filename=home + '\\' + 'Ekahau.log', encoding='utf-8', filemode='w', level=logging.DEBUG)
    if len(sys.argv) == 3:
        logging.debug('Correct number of arguments supplied')
        wlc_config_filename = home + '\\' + sys.argv[1]
        project_filename = home + '\\' + sys.argv[2]
        bssid_dict = exctract_bssid(wlc_config_filename)
        if len(bssid_dict) > 0:
            add_ap_names(project_filename,bssid_dict)
        else:
            print('No BSSID found in supplied WLC config file')
            logging.debug('No BSSID found in supplied WLC config file')
    else:
        print('Incorrect number of arguments supplied, please check README for instructions')
        logging.debug('!!! INCorrect number of arguments supplied: ' + str(len(sys.argv)))

if __name__ == "__main__":
    main()