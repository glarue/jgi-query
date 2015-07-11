#!/usr/bin/env python2

"""
Retrieves files/directories from JGI through the curl api.

"""
import sys
import os
import re
import subprocess
import textwrap
import xml.etree.ElementTree as ET
from collections import defaultdict

def usage_blurb():
    print '*'*80
    print
    print textwrap.dedent("""\
        This script will retrieve files from JGI using the curl api. It will
        return a list of possible files for downloading.
        
        Usage:
        
        $ jgi-query.py [<jgi_address_of_organism>, <jgi_name_of_organism>] [-xml [<your_xml>]]
        
        To get <jgi_address_of_organism>, go to: http://genome.jgi.doe.gov/
        and search for your species of interest. Click through until
        you are at the main page. For \x1B[3mNematostella vectensis\x1B[23m, the
        desired page is "http://genome.jgi.doe.gov/Nemve1/Nemve1.info.html".

        To query using only the name simply requires the specific JGI
        organism abbreviation, as referenced in the full url.
        
        For the above example, the ways to run this script would be:
        
        $ jgi-query.py http://genome.jgi.doe.gov/Nemve1/Nemve1.info.html

                                 -or-

        $ jgi-query.py Nemve1

        * If you already have the xml file for the query in the directory,
        use the -xml flag to avoid redownloading it:

        $ jgi-query.py -xml <your_xml_index>

        If the xml filename is omitted when using the -xml flag, it is assumed
        that the xml file is named '<org_name>_jgi_index.xml'""")
    print
    print '*'*80

if len(sys.argv) < 2:
    usage_blurb()
    sys.exit(0)

org_address = sys.argv[1]
try:
    organism = re.search("\.jgi.+\.(?:gov|org)/(.+)/", org_address).group(1)
except AttributeError:  # not in address form, assume string is name
    organism = org_address

# CONFIG
def check_config(d, config_name):
    files = os.listdir(d)
    if config_name in files:
        config_path = d + "/{}".format(config_name)
        return config_path
    else:
        return None

def get_user_info():
    blurb = ("\n== USER SETUP ==\n\n"
             "It appears that this script has yet to be configured.\n"
             "Before continuing, you will need to provide your JGI login credentials.\n"
             "They are required by JGI's curl api, and will be stored in a config\n"
             "file for future use (unless of course you choose to delete them).\n\n"
             "If you need to sign up for a JGI account use the registration link at\n"
             "https://signon.jgi-psf.org/signon\n"
             "\n== USER CREDENTIALS ==\n")
    print blurb
    user_query = "JGI account username/email (or 'q' to quit): "
    pw_query = "JGI account password (or 'q' to quit): "
    user = raw_input(user_query)
    if user == "q":
        sys.exit("Exiting now.")
    pw = raw_input(pw_query)
    if pw == "q":
        sys.exit("Exiting now.")
    input_blurb = ("Use USER = '{}', PASSWORD = '{}' to configure script?\n"
                   "(y=yes, n=exit, r=restart): ".format(user, pw))
    user_info = {"user": user, "password": pw}
    choice = raw_input(input_blurb)
    if choice.lower() == "r":
        user_info = get_user_info()
        return user_info
    if choice.lower() == "n":
        sys.exit("Exiting now.")
    if choice.lower() == "y":
        return user_info

def make_config(config_path, user_info):
    """
    Creates a config file <config_name> in directory
    <d> using credentials from <user_info>.

    """
    u = user_info["user"]
    p = user_info["password"]
    header = "# jgi-query.py user configuration information\n"
    config_info = "user={}\npassword={}".format(u, p)
    with open(config_path, 'w') as config:
        config.write(header)
        config.write(config_info)

def read_config(config):
    with open(config) as c:
        for line in c:
            line = line.strip()
            if line.startswith("user"):
                user = line.split("=")[1]
            if line.startswith("password"):
                pw = line.split("=")[1]
    if not (user and pw):
        sys.exit("ERROR: Config file present ({}), but user and/or password not found."
                 .format(config))
    user_info = {"user": user, "password": pw}
    return user_info

# Get script location info
SCRIPT_PATH = os.path.realpath(sys.argv[0])
SCRIPT_HOME = os.path.dirname(SCRIPT_PATH)

# Config should be in same directory as script
CONFIG_FILENAME = "jgi-query.config"
CONFIG_FILEPATH = SCRIPT_HOME + "/{}".format(CONFIG_FILENAME)

# Does config file exist?
if os.path.isfile(CONFIG_FILEPATH):  # use config file
    user_info = read_config(CONFIG_FILEPATH)
else:  # no config present; run config dialog
    user_info = get_user_info()
    make_config(CONFIG_FILEPATH, user_info)
# /CONFIG


# Get user information for sign-on
USER = user_info["user"]
PASSWORD = user_info["password"]

# # Modify these to change the login credentials
# USER = 'roylabsfsu@gmail.com'
# PASSWORD = 'splice!@#$sfsu'

# Set curl login string using user/pw
LOGIN_STRING = 'curl https://signon.jgi.doe.gov/signon/create --data-ascii'\
        ' login={}\&password={} -b cookies -c cookies >'\
        ' /dev/null'.format(USER, PASSWORD)

# Get xml index of files, using existing local file or curl api
if "-xml" in sys.argv:
    local_xml = True
else:
    local_xml = False
if not local_xml:  # retrieve from Internet
    xml_index_filename = '{}_jgi_index.xml'.format(organism)
    xml_address = 'curl'\
        ' http://genome.jgi.doe.gov/ext-api/downloads/get-directory?organism={}'\
        ' -b cookies -c cookies > {}'.format(organism, xml_index_filename)
    subprocess.call(LOGIN_STRING, shell=True)
    subprocess.call(xml_address, shell=True)
else:
    xml_arg = sys.argv.index("-xml") + 1
    try:
        xml_index_filename = sys.argv[xml_arg]
    except IndexError:  # -xml flag used without argument
        xml_index_filename = '{}_jgi_index.xml'.format(organism)


# # Deprecated method, kept as reference
# def file_list(categories):
#     descriptors = {}
#     uid = 0
#     for c in categories:
#         descriptors[c] = {}
#         for e in root.findall(".//file/..[@name='{}']".format(c)):
#             for i in e:
#                 try:
#                     descriptors[c][uid]
#                 except KeyError:
#                     descriptors[c][uid] = {}
#                 ids = i.attrib
#                 descriptors[c][uid]['filename'] = ids['filename']
#                 descriptors[c][uid]['url'] = ids['url']
#                 descriptors[c][uid]['size'] = ids['size']
#                 uid += 1
#     return descriptors

# NOW WITH RECURSION
def recursive_hunt(parent, key, matches=None):  # original: matches={}
    """
    This moves through the XML tree and pulls
    out entries with name=<key>. Returns a
    dict of matches.

    """
    for child in parent.getchildren():
        # print child.attrib['name']
        try:
            if child.attrib['name'] == key:
                parent_name = parent.attrib['name']
                for grandchild in child.getchildren():
                    if 'filename' not in grandchild.attrib:
                        continue
                    try:
                        matches[parent_name].append(grandchild.attrib)
                    except KeyError:
                        matches[parent_name] = [grandchild.attrib]
            else:
                # parent_name = None
                recursive_hunt(child, key, matches)
        except KeyError:
            return matches
    return matches


def get_file_list(root_file, categories):
    descriptors = {}
    display_cats = ['filename', 'url', 'size', 'label', 'sizeInBytes']
    category_id = 0
    for c in sorted(categories):
        category_id += 1
        found = recursive_hunt(root_file, c, matches={})  # matches={} important!
        if not found.values():
            continue
        descriptors[c] = defaultdict(dict)
        descriptors[c]["catID"] = category_id
        uid = 1
        for parent, children in sorted(found.iteritems()):
            descriptors[c]["results"][parent] = defaultdict(dict)
            results = descriptors[c]["results"][parent]
            children = [e for e in children if 'filename' in e]
            for child in sorted(children, key=lambda x: x['filename']):
                try:
                    results[uid]
                except KeyError:
                    results[uid] = {}
                for dc in display_cats:
                    try:
                        results[uid][dc] = child[dc]
                    except KeyError:
                        continue
                uid += 1
    return descriptors

def get_sizes(d, sizes_by_url={}):
    """
    Builds a dictionary of url:sizes from
    output of get_file_list()

    """
    for k, v in d.iteritems():
        if isinstance(v, dict):
            if 'url' in v:
                address = v['url']
                size = int(v['sizeInBytes'])
                sizes_by_url[address] = size
            else:
                get_sizes(v, sizes_by_url)
    return sizes_by_url

def cleanExit(exit_message=None):
    # subprocess.call('rm {} {}'.format(xml_index_filename, 'cookies'), shell=True)
    to_remove = ["cookies"]
    if not local_xml:  # don't delete xml file if supplied by user
        to_remove.append(xml_index_filename)
    for f in to_remove:
        try:
            os.remove(f)
        except OSError:
            continue
    if exit_message:
        print_message = "{}\n".format(exit_message)
    else:
        print_message = ""
    sys.exit("{}Removing temp files and exiting".format(print_message))

# Parse xml file for files to download
try:
    xml_in = ET.parse(xml_index_filename)
    xml_root = xml_in.getroot()
except:
    cleanExit("Cannot parse xml file. Make sure file exists and has content.")

# Build local file info
desired_categories = ['ESTs',
                      'EST Clusters',
                      'Assembled scaffolds (unmasked)',
                      'Assembled scaffolds (masked)',
                      'Transcripts',
                      'Genes',
                      'CDS',
                      'Proteins',
                      'Additional Files']
file_list = get_file_list(xml_root, desired_categories)

# Check if file has any categories of interest
if not any(v["results"] for v in file_list.values()):
    print ("ERROR: no results found for '{}' in any of the following "
           "categories:\n---\n{}\n---"
           .format(organism, "\n".join(desired_categories)))
    cleanExit()

file_sizes = get_sizes(file_list, sizes_by_url={})

def print_data(data, org_name):
    print "QUERY RESULTS FOR '{}'\n".format(org_name)
    dict_to_get = {}
    for query_cat, v in sorted(data.iteritems(), key=lambda (k, v): v["catID"]):
        if not v["results"]:
            continue
        catID = v["catID"]
        dict_to_get[catID] = {}
        print " {}: {} ".format(catID, query_cat).center(80, "=")
        results = v["results"]
        for sub_cat, items in sorted(results.iteritems(),
                                     key=lambda (sub_cat, items): items.items()[0]):
            print "# {}:".format(sub_cat)
            for index, i in sorted(items.iteritems()):
                # name = i["label"]
                # size = i["size"]
                dict_to_get[catID][index] = i["url"]
                print_index = "[{}]".format(str(index))
                size = "({})".format(i["size"])
                filename = i["filename"]
                margin = 80 - (len(size) + len(print_index))
                file_info = filename.center(margin, "-")
                print "".join([print_index, file_info, size])
            print  # padding
    return dict_to_get


# Ask user which files to download from xml

long_blurb = """
# USAGE #######################################################################

# Select one or more of the following to download, using the
# following format:
#     <category number>:<indices>;<category number>:<indices>;...

# Indices may be a mixture of comma-separated values and hyphen-
# separated ranges.

# For example, consider the following results:


=================================== 6: Genes ===================================
# All models, Filtered and Not:
[1]-----------------------Nemve1.AllModels.gff.gz------------------------(20 MB)

# Filtered Models ("best"):
[2]---------------------Nemve1.FilteredModels1.gff.gz---------------------(3 MB)
[3]----------------------Nvectensis_19_PAC2_0.GFF3.gz---------------------(2 MB)

================================ 7: Transcripts ================================
# All models, Filtered and Not:
[1]-----------------transcripts.Nemve1AllModels.fasta.gz-----------------(55 MB)

# Filtered Models ("best"):
[2]---------------transcripts.Nemve1FilteredModels1.fasta.gz--------------(8 MB)


# To retrieve items 1 and 2 from 'Genes' and 2 from 'Transcripts', the query
should be: '6:1,2; 7:2'

# /USAGE ######################################################################
"""
select_blurb = """
# SYNTAX ######################################################################

# Select one or more of the following to download, using the
# following format:
#     <category number>:<indices>;<category number>:<indices>;...

# Indices may be a mixture of comma-separated values and hyphen-
# separated ranges.

# Example: '3:4,5; 7:1-10,13' will select elements 4 and 5 from
# category 3, and 1-10 as well as 13 from category 7.

# /SYNTAX #####################################################################
"""

print long_blurb
url_dict = print_data(file_list, organism)

def get_user_choice():
    choice = raw_input("Enter file selection ('q' to quit, 'usage' to review syntax):\n>")
    if choice == "usage":
        print
        print select_blurb
        print
        return get_user_choice()
    elif choice.lower() in ("q", "quit", "exit"):
        cleanExit()
    else:
        return choice

user_choice = get_user_choice()

def parse_selection(user_input):
    selections = {}
    parts = user_input.split(";")
    for p in parts:
        if len(p.split(":")) > 2:
            cleanExit("FATAL ERROR: can't parse desired input\n?-->'{}'".format(p))
        category, indices = p.split(":")
        category = int(category)
#         print category
        selections[category] = []
        cat_list = selections[category]
        indices = indices.split(",")
        for i in indices:
            try:
                cat_list.append(int(i))  # if it's already an integer
            except ValueError:
                try:
                    start, stop = map(int, i.split("-"))
                except:
                    cleanExit("FATAL ERROR: can't parse desired input\n?-->'{}'".format(i))
                add_range = range(start, stop + 1)
                for e in add_range:
                    cat_list.append(e)
    return selections

ids_dict = parse_selection(user_choice)
urls_to_get = []
for k, v in sorted(ids_dict.iteritems()):
    for i in v:
        urls_to_get.append(url_dict[k][i])

# Calculate total size of selected data
total_size = 0
for url in urls_to_get:
    total_size += file_sizes[url]
adjusted = round(total_size/1000000.0, 2)
if adjusted < 1000:
    unit = "MB"
else:
    adjusted = round(adjusted/1000, 2)
    unit = "GB"
size_string = "{} {}".format(adjusted, unit)
print ("Total download size of selected files: {}".format(size_string))
download = raw_input("Continue? (y/n)")
if download.lower() != "y":
    cleanExit("ABORTING DOWNLOAD")

# Run curl commands to retrieve selected files
downloaded_files = []

for url in urls_to_get:
    filename = re.search('.+/(.+$)', url).group(1)
    downloaded_files.append(filename)
    print 'Downloading \'{}\'\n'.format(filename)
    download_command = 'curl http://genome.jgi.doe.gov{} -b cookies'\
                       ' -c cookies > {}'.format(url, filename)
# The next line doesn't appear to be needed to refresh the cookies.
#    subprocess.call(login, shell=True)
    subprocess.call(download_command, shell=True)

def unzip_files(local_file_list):
    for e in local_file_list:
        if re.search('(?<!tar)\.gz$', e):
            subprocess.call(['gunzip', e])

print 'Finished downloading all files.'
unzip = raw_input('Unzip all downloaded files? (y/n): ')
if unzip == 'y':
    unzip_files(downloaded_files)
    print 'Finished unzipping all files.'

# Clean up and exit
keep_temp = "n"
keep_temp = raw_input("Keep temporary files ('{}' and 'cookies') (y/n)?\n>"
                      .format(xml_index_filename))
if keep_temp.lower() not in "y, yes":
    cleanExit()
else:
    print 'Leaving temporary files intact and exiting.'

sys.exit(0)
