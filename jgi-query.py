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
import argparse
import tarfile
import gzip

# FUNCTIONS

def deindent(string):
    """
    Print left-justified triple-quoted text blocks

    """
    print textwrap.dedent(string)

def check_config(d, config_name):
    """
    Check filesystem for existence of configuration
    file, and return the full path of config file
    if found.

    """
    files = os.listdir(d)
    if config_name in files:
        config_path = d + "/{}".format(config_name)
        return config_path
    else:
        return None

def get_user_info():
    """
    Dialog with user to gather user information for
    use with the curl query. Returns a dict.

    """
    blurb = """
    === USER SETUP ===

    JGI access configuration:

    Before continuing, you will need to provide your JGI login credentials.
    These are required by JGI's curl api, and will be stored in a config
    file for future use (unless you choose to delete them).

    If you need to sign up for a JGI account, use the registration link at
    https://signon.jgi-psf.org/signon

    === CREDENTIALS ===
    """
    deindent(blurb)
    user_query = "JGI account username/email (or 'q' to quit): "
    pw_query = "JGI account password (or 'q' to quit): "
    user = raw_input(user_query)
    if user == "q":
        sys.exit("Exiting now.")
    pw = raw_input(pw_query)
    if pw == "q":
        sys.exit("Exiting now.")
    input_blurb = ("Proceed with USER='{}', PASSWORD='{}' to configure script?\n"
                   "([y]es, [n]o, [r]estart): ".format(user, pw))
    user_info = {"user": user, "password": pw}
    while True:  # catch invalid responses
        choice = raw_input(input_blurb)
        if choice.lower() == "r":
            user_info = get_user_info()
            return user_info
        if choice.lower() == "n":
            sys.exit("Exiting now.")
        if choice.lower() == "y":
            return user_info

def make_config(config_path, config_info):
    """
    Creates a config file <config_path> using
    credentials from dict <config_info>.

    """
    u = config_info["user"]
    p = config_info["password"]
    c = config_info["categories"]
    c = ",".join(c)
    header = "# jgi-query.py user configuration information {}\n".format("#" * 34)
    info = "user={}\npassword={}\ncategories={}".format(u, p, c)
    with open(config_path, 'w') as config:
        config.write(header)
        config.write(info)

def read_config(config):
    """
    Reads "user", "password" and "categories" entries
    from config file.

    """
    user, pw, categories = None, None, None
    with open(config) as c:
        for line in c:
            line = line.strip()
            if line.startswith("user"):
                user = line.split("=")[1]
            if line.startswith("password"):
                pw = line.split("=")[1]
            if line.startswith("categories"):
                cats = line.strip().split("=")[1]
                categories = [e.strip() for e in cats.split(",")]
    if not (user and pw):
        sys.exit("ERROR: Config file present ({}), but user and/or password not found."
                 .format(config))
    config_info = {"user": user, "password": pw, "categories": categories}
    return config_info

# /CONFIG

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
def recursive_hunt(parent, key, matches=None):
    """
    This moves through the XML tree and pulls
    out entries with name=<key>. Returns a
    dict of matches with parent name as key.

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
    """
    Moves through the xml document <root_file> and returns information
    about matches to elements in <categories>.

    """
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

# Work in progress - doesn't organize files particularly well due to
# inconsistent parent nesting levels in certain XML files
# Will get *all* files, instead of working from a list of categories
def recursive_hunt_all(root, parents=None, matches=None, level=1, reset=True):
    """
    Gets list of all XML entries with "filename" attribute,
    and returns a dictionary of the file attributes keyed
    by a ":"-joined string of parent names.

    """
    for c in root.getchildren():
        base_level = level
        if "filename" not in c.attrib:
            try:  # if name, is one of parents
                parents.append(c.attrib['name'])
            except KeyError:
                pass
            recursive_hunt_all(c, parents, matches, level + 1, reset=True)
        else:
            reset = False
            parent_string = ":".join(parents)
            try:
                matches[parent_string].append(c.attrib)
            except KeyError:
                matches[parent_string] = [c.attrib]
        if reset:  # only true if out of files block
            level -= 1
            parents = parents[:level]
        level = base_level  # this gets the correct levels of all folders
    return matches

def format_found(d):
    """
    Reformats the output from recursive_hunt_all()

    """
    output = {}
    for p, c in sorted(d.iteritems()):
        layers = [e for e in p.split(":") if e]
        top = layers[-1]
        if len(layers) < 2:
            parent = top
        else:
            parent = layers[-2]
        if top not in output:
            output[top] = defaultdict(dict)
        output[top][parent] = c
    return output

# Goes with recursive_hunt_all()
def get_file_list_all(root_file):
    """
    Moves through the xml document <root_file> and returns information
    about matches to elements in <categories>.

    """
    descriptors = {}
    display_cats = ['filename', 'url', 'size', 'label', 'sizeInBytes']
    found = recursive_hunt_all(root_file, parents=[], matches={})
    found = format_found(found)
    if not found.values():
        return None
    category_id = 0
    for category, sub_cat in sorted(found.iteritems()):
        c = category
        category_id += 1
        descriptors[c] = defaultdict(dict)
        descriptors[c]["catID"] = category_id
        uid = 1
        for parent, children in sorted(sub_cat.iteritems()):
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

def get_sizes(d, sizes_by_url=None):  # original, unsafe: sizes_by_url={}
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

def extract_file(file_path, keep_compressed=False):
    """
    Native Python file decompression for tar.gz and .gz files.

    To do: implement .zip decompression

    """
    tar_pattern = 'tar.gz$'  # matches tar.gz
    gz_pattern = '(?<!tar)\.gz$'  # excludes tar.gz
    endings_map = {"tar": (tarfile, "r:gz", ".tar.gz"),
                   "gz": (gzip, "rb", ".gz")
                  }
    if re.search(tar_pattern, file_path):
        opener, mode, ext = endings_map["tar"]
    elif re.search(gz_pattern, file_path):
        opener, mode, ext = endings_map["gz"]
    else:
        raise ValueError("No decompression implemented for '{}'".format(file_path))
    out_name = file_path.rstrip(ext)
    with opener.open(file_path) as f, open(out_name, "wb") as out:
        for l in f:
            out.write(l)
    if not keep_compressed:
        os.remove(file_path)

def decompress_files(local_file_list, keep_original=False):
    """
    Decompresses list of files, and deletes compressed
    copies unless <keep_original> is True.

    """
    for f in local_file_list:
        extract_file(f, keep_original)

def print_data(data, org_name):
    """
    Prints info from dict. <data> in a specific format.
    Also returns a dict with url information for every file
    in desired categories.

    """
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
                dict_to_get[catID][index] = i["url"]
                print_index = "[{}]".format(str(index))
                size = "({})".format(i["size"])
                filename = i["filename"]
                margin = 80 - (len(size) + len(print_index))
                file_info = filename.center(margin, "-")
                print "".join([print_index, file_info, size])
            print  # padding
    return dict_to_get

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

def parse_selection(user_input):
    """
    Parses the user choice string and returns a dictionary
    of categories (keys) and choices within each category
    (values).

    """
    selections = {}
    parts = user_input.split(";")
    for p in parts:
        if len(p.split(":")) > 2:
            cleanExit("FATAL ERROR: can't parse desired input\n?-->'{}'".format(p))
        category, indices = p.split(":")
        category = int(category)
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

# /FUNCTIONS

# BLURBS

usage_example_blurb = """\
This script will retrieve files from JGI using the cURL api. It will
return a list of possible files for downloading.

* This script depends upon cURL - it can be downloaded here:
http://curl.haxx.se/

Usage /////////////////////////////////////////////////////////////////////////

$ jgi-query.py [<jgi_address>, <jgi_abbreviation>] [[-xml [<your_xml>]], -a]

To get <jgi_address>, go to: http://genome.jgi.doe.gov/ and search for your
species of interest. Click through until you are at the "Info" page. For
\x1B[3mNematostella vectensis\x1B[23m, the appropriate page is
"http://genome.jgi.doe.gov/Nemve1/Nemve1.info.html".

To query using only the name simply requires the specific JGI organism
abbreviation, as referenced in the full url.

For the above example, the ways to run this script would be:

$ jgi-query.py http://genome.jgi.doe.gov/Nemve1/Nemve1.info.html

                         -or-

$ jgi-query.py Nemve1

* If you already have the xml file for the query in the directory,
you may use the -xml flag to avoid redownloading it:

$ jgi-query.py -xml <your_xml_index>

If the XML filename is omitted when using the -xml flag, it is assumed
that the XML file is named '<jgi_abbreviation>_jgi_index.xml'"""


long_blurb = """
# USAGE ///////////////////////////////////////////////////////////////////////

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
# should be: '6:1,2; 7:2'

# /USAGE //////////////////////////////////////////////////////////////////////
"""

select_blurb = """
# SYNTAX //////////////////////////////////////////////////////////////////////

Select one or more of the following to download, using the following format:

    <category number>:<i>[,<i>, <i>];<category number>:<i>-<i>;...

Indices (<i>) may be a mixture of comma-separated values and hyphen-
separated ranges.

Example: '3:4,5; 7:1-10,13' will select elements 4 and 5 from category 3, and
1-10, 13 from category 7.

# /SYNTAX /////////////////////////////////////////////////////////////////////
"""

# /BLURBS

# ARG PARSER
parser = argparse.ArgumentParser(
    description="This script will list and retrieve files from JGI using the "
                "curl API. It will return a list of all files available for "
                "download for a given query organism.",
    formatter_class=argparse.ArgumentDefaultsHelpFormatter)
parser.add_argument("organism_abbreviation", nargs='?',
                    help="organism name formatted per JGI's abbreviation. For "
                         "example, 'Nematostella vectensis' is abbreviated by "
                         "JGI as 'Nemve1'. The appropriate abbreviation may be "
                         "found by searching for the organism on JGI; the name "
                         "used in the URL of the 'Info' page for that organism "
                         "is the correct abbreviation. The full URL may also be "
                         "used for this argument")
parser.add_argument("-x", "--xml", nargs='?', const=1,
                    help="specify a local xml file for the query instead of "
                         "retrieving a new copy from JGI")
parser.add_argument("-c", "--configure", action='store_true',
                    help="initiate configuration dialog to overwrite existing "
                         "user/password configuration")
parser.add_argument("-s", "--syntax_help", action='store_true')
parser.add_argument("-a", "--all_files", action='store_true',
                    help="don't filter organism results by top "
                         "categories and instead report all files listed by JGI "
                         "for the query (work in progress)")
parser.add_argument("-u", "--usage", action='store_true',
                    help="print verbose usage information and exit")

# /ARG PARSER

# Check arguments and exit if too short
if len(sys.argv) == 1:
    parser.print_help()
    sys.exit(1)

args = parser.parse_args()

# Check if user wants query help
if args.syntax_help:
    sys.exit(select_blurb)
if args.usage:
    sys.exit(usage_example_blurb)

# CONFIG

# Get script location info
SCRIPT_PATH = os.path.realpath(sys.argv[0])
SCRIPT_HOME = os.path.dirname(SCRIPT_PATH)

# Config should be in same directory as script
CONFIG_FILENAME = "jgi-query.config"
CONFIG_FILEPATH = SCRIPT_HOME + "/{}".format(CONFIG_FILENAME)

# Categories to store in default config file
DEFAULT_CATEGORIES = ['ESTs',
                      'EST Clusters',
                      'Assembled scaffolds (unmasked)',
                      'Assembled scaffolds (masked)',
                      'Transcripts',
                      'Genes',
                      'CDS',
                      'Proteins',
                      'Additional Files']

# Does config file exist?
if os.path.isfile(CONFIG_FILEPATH) and not args.configure:  # use config file
    config_info = read_config(CONFIG_FILEPATH)
else:  # no config present or configure flag used; run config dialog
    config_info = get_user_info()
    config_info["categories"] = DEFAULT_CATEGORIES
    make_config(CONFIG_FILEPATH, config_info)

# /CONFIG

# Get user information for sign-on
USER = config_info["user"]
PASSWORD = config_info["password"]

# Set curl login string using user and password as per https://goo.gl/oppZ2a
LOGIN_STRING = 'curl https://signon.jgi.doe.gov/signon/create --data-ascii'\
               ' login={}\&password={} -b cookies -c cookies >'\
               ' /dev/null'.format(USER, PASSWORD)

# Get organism name for query
org_input = args.organism_abbreviation
if not org_input:
    if args.configure:
        sys.exit("Configuration complete. Script may now be used to query JGI. "
                 "Exiting now.")
    else:
        sys.exit("No organism specified. Exiting now.")
try:  # see if it's in address form
    organism = re.search("\.jgi.+\.(?:gov|org)/(.+)/", org_input).group(1)
except AttributeError:  # not in address form, assume string is organism name
    organism = org_input

# URL where remote XML file should be, if it exists
org_url = ("http://genome.jgi.doe.gov/ext-api/downloads/get-directory?organism={}"
           .format(organism))


# Get xml index of files, using existing local file or curl API
# if "-xml" in sys.argv:
if args.xml:
    local_xml = True  # global referenced by cleanExit()
else:
    local_xml = False
if not local_xml:  # retrieve from JGI
    xml_index_filename = '{}_jgi_index.xml'.format(organism)
    xml_address = ("curl {} -b cookies -c cookies > {}"
                   .format(org_url, xml_index_filename))
    try:  # fails if unable to contact server
        subprocess.check_output(LOGIN_STRING, shell=True)
    except subprocess.CalledProcessError as error:
        cleanExit("Couldn't connect with server. Please check Internet connection "
                  "and retry.")
    subprocess.call(xml_address, shell=True)
else:
    xml_arg = args.xml
    if xml_arg == 1: # -xml flag used without argument
        xml_index_filename = '{}_jgi_index.xml'.format(organism)
    else:
        xml_index_filename = xml_arg

# Parse xml file for content to download
xml_root = None
if os.path.getsize(xml_index_filename) == 0:  # happens if user and/or pw wrong
    # os.remove(CONFIG_FILEPATH)  # instruct user to overwrite with -c instead
    cleanExit("Invalid username/password combination.\n"
              "Please restart script with flag '-c' to reconfigure credentials.")
try:
    xml_in = ET.ElementTree(file=xml_index_filename)
    xml_root = xml_in.getroot()
except ET.ParseError:  # organism not found/xml file contains errors
    cleanExit("Cannot parse XML file or no organism match found.\n"
              "Ensure remote file exists and has content at the following address:\n"
              "{}".format(org_url))

# Get categories from config (including possible user additions)
DESIRED_CATEGORIES = config_info["categories"]

# Choose between different XML parsers
if args.all_files:  # user wants every file listed, not just those in <desired_categories>
    file_list = get_file_list_all(xml_root)
else:
    file_list = get_file_list(xml_root, DESIRED_CATEGORIES)

# Check if file has any categories of interest
if not any(v["results"] for v in file_list.values()):
    print ("ERROR: no results found for '{}' in any of the following "
           "categories:\n---\n{}\n---"
           .format(organism, "\n".join(DESIRED_CATEGORIES)))
    cleanExit()

file_sizes = get_sizes(file_list, sizes_by_url={})

# Ask user which files to download from xml
print long_blurb
print  # padding
url_dict = print_data(file_list, organism)

user_choice = get_user_choice()

# Retrieve user-selected file urls from dict
ids_dict = parse_selection(user_choice)
urls_to_get = []
for k, v in sorted(ids_dict.iteritems()):
    for i in v:
        urls_to_get.append(url_dict[k][i])

# Calculate and display total size of selected data
total_size = sum([file_sizes[url] for url in urls_to_get])
adjusted = total_size/1e6  # bytes to MB
if adjusted < 1000:
    unit = "MB"
else:
    adjusted /= 1000
    unit = "GB"
size_string = "{:.2f} {}".format(adjusted, unit)
print ("Total download size of selected files: {}".format(size_string))
download = raw_input("Continue? (y/n): ")
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

print 'Finished downloading all files.'

# Kindly offer to unpack files
decompress = raw_input('Decompress all downloaded files? (y/n/k=decompress and keep original): ')
if decompress != "n":
    if decompress == "k":
        keep_original = True
    else:
        keep_original = False
    decompress_files(downloaded_files, keep_original)
    print 'Finished decompressing all files.'

# Clean up and exit
# "cookies" file is always created
keep_temp = raw_input("Keep temporary files ('{}' and 'cookies')? (y/n): "
                      .format(xml_index_filename))
if keep_temp.lower() not in "y, yes":
    cleanExit()
else:
    print 'Leaving temporary files intact and exiting.'

sys.exit(0)
