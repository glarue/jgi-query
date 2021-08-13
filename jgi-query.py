#!/usr/bin/env python3

"""
Retrieves files/directories from JGI through the curl api.

"""
import sys
import os
import re
import subprocess
import textwrap
import xml.etree.ElementTree as ET
import argparse
import tarfile
import gzip
import time
import readline  # allows arrow keys to be used during input
from collections import defaultdict
from hashlib import md5

# FUNCTIONS

def deindent(string):
    """
    Print left-justified triple-quoted text blocks

    """
    print(textwrap.dedent(string))


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
    https://contacts.jgi.doe.gov/registration/new

    === CREDENTIALS ===
    """
    deindent(blurb)
    user_query = "JGI account username/email (or 'q' to quit): "
    pw_query = "JGI account password (or 'q' to quit): "
    user = input(user_query)
    if user == "q":
        sys.exit("Exiting now.")
    pw = input(pw_query)
    if pw == "q":
        sys.exit("Exiting now.")
    input_blurb = ("Proceed with USER='{}', PASSWORD='{}' to configure "
                   "script?\n([y]es, [n]o, [r]estart): ".format(user, pw))
    user_info = {"user": user, "password": pw}
    while True:  # catch invalid responses
        choice = input(input_blurb)
        if choice.lower() == "y":
            return user_info
        elif choice.lower() == "n":
            sys.exit("Exiting now.")
        elif choice.lower() == "r":
            user_info = get_user_info()


def make_config(config_path, config_info):
    """
    Creates a config file <config_path> using
    credentials from dict <config_info>.

    """
    u = config_info["user"]
    p = config_info["password"]
    c = config_info["categories"]
    c = ",".join(c)
    header = ("# jgi-query.py user configuration information {}\n"
              .format("#" * 34))
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
        sys.exit("ERROR: Config file present ({}), but user and/or "
                 "password not found.".format(config))
    config_info = {"user": user, "password": pw, "categories": categories}
    return config_info


# /CONFIG

def xml_hunt(xml_file):
    """
    Gets list of all XML entries with "filename" attribute,
    and returns a dictionary of the file attributes keyed
    by a ":"-joined string of parent names.

    """
    root = ET.iterparse(xml_file, events=("start", "end"))
    parents = []
    matches = {}
    for event, element in root:
        if element.tag not in ["folder", "file"]:  # skip topmost categories
            continue
        if element.tag == "folder":
            if event == "start":  # add to parents
                parents.append(element.attrib["name"])
            elif event == "end":  # strip from parents
                del parents[-1]
            continue
        if event == "start" and element.tag == "file":
            parent_string = ":".join(parents)
            try:
                matches[parent_string].append(element.attrib)
            except KeyError:
                matches[parent_string] = [element.attrib]
    return matches


def format_found(d, filter_found=False):
    """
    Reformats the output from xml_hunt()

    """
    output = {}
    for p, c in sorted(d.items()):
        layers = [e for e in p.split(":") if e]
        if filter_found:
            if not any(cat in layers for cat in DESIRED_CATEGORIES):
                continue
        if len(layers) == 1:
            top = parent = layers[0]
        else:
            top = layers[-2]  # either -2 or -1 works well, != parent
            parent = layers[-1]  # either -2 or -1 works well, != top
        if top not in output:
            output[top] = defaultdict(dict)
        if parent not in output[top]:
            output[top][parent] = c
        else:
            output[top][parent].extend(c)
    return output


def get_file_list(xml_file, filter_categories=False):
    """
    Moves through the xml document <xml_file> and returns information
    about matches to elements in <DESIRED_CATEGORIES> if
    <filter_categories> is True, or all files otherwise

    """
    descriptors = {}
    display_cats = ['filename', 'url', 'size',
                    'label', 'sizeInBytes', 'timestamp', 'md5']
    found = xml_hunt(xml_file)
    found = format_found(found, filter_categories)
    if not list(found.values()):
        return None
    category_id = 0
    for category, sub_cat in sorted(found.items()):
        c = category
        if c not in descriptors:
            category_id += 1
            descriptors[c] = defaultdict(dict)
            descriptors[c]["catID"] = category_id
        uid = 1
        for parent, children in sorted(sub_cat.items()):
            descriptors[c]["results"][parent] = defaultdict(dict)
            results = descriptors[c]["results"][parent]
            unique_children = uniqueify(children)
            for child in sorted(unique_children, key=lambda x: x['filename']):
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


def uniqueify(children):
    """
    Takes a list of child XML elements (dicts of attribs) as 
    returns a filtered list of only unique filenames for a given 
    month/year timestamp (e.g. duplicates are allowed if month/year 
    is different).
    
    """
    unique = {}
    for child in children:
        try:
            fn = child['filename']
            date = fmt_timestamp(child['timestamp'])
            date_string = (date.tm_mon, date.tm_year)
            uid = (fn, date_string)
        except KeyError:
            continue
        if fn not in unique:
            unique[uid] = child
        else:
            existing = unique[uid].get('fileType', None)
            if existing == 'Unknown':
                existing = None
            current = child.get('fileType', None)
            if current == 'Unknown':
                current = None
            if current is not None and existing is None:
                unique[uid] = child
        
    return unique.values()


def get_sizes(d, sizes_by_url=None):
    """
    Builds a dictionary of url:sizes from
    output of get_file_list()

    """
    for k, v in d.items():
        if isinstance(v, dict):
            if 'url' in v:
                address = v['url']
                size = int(v['sizeInBytes'])
                sizes_by_url[address] = size
            else:
                get_sizes(v, sizes_by_url)
    return sizes_by_url


def clean_exit(exit_message=None, remove_temp=True):
    """
    Perform a sys.exit() while removing temporary files and
    informing the user.

    """
    to_remove = ["cookies"]
    # don't delete xml file if supplied by user
    if not LOCAL_XML and remove_temp is True:
        try:
            to_remove.append(xml_index_filename)
        except NameError:
            pass
    for f in to_remove:
       try:
           os.remove(f)
       except OSError:
           continue
    if exit_message:
        print_message = "{}\n".format(exit_message)
    else:
        print_message = ""

    print("{}Removing temp files and exiting".format(print_message))
    sys.exit(0)
    

def extract_file(file_path, keep_compressed=False):
    """
    Native Python file decompression for tar.gz and .gz files.

    TODO: implement .zip decompression

    """
    tar_pattern = 'tar.gz$'  # matches tar.gz
    gz_pattern = '(?<!tar)\.gz$'  # excludes tar.gz
    endings_map = {"tar": (tarfile, "r:gz", ".tar.gz"),
                   "gz": (gzip, "rb", ".gz")
                   }
    relative_name = os.path.basename(file_path)
    if re.search(tar_pattern, file_path):
        opener, mode, ext = endings_map["tar"]
        with opener.open(file_path) as f:
            file_count = len(f.getmembers())
            if file_count > 1:  # make sub-directory to unpack into
                dir_name = relative_name.rstrip(ext)
                try:
                    os.mkdir(dir_name)
                except FileExistsError:
                    pass
                destination = dir_name
            else:  # single file, extract into working directory
                destination = "."
            f.extractall(destination)
    elif re.search(gz_pattern, file_path):
        opener, mode, ext = endings_map["gz"]
        # out_name = file_path.rstrip(ext)
        out_name = relative_name.rstrip(ext)
        with opener.open(file_path) as f, open(out_name, "wb") as out:
            for l in f:
                out.write(l)
    else:
        print("Skipped decompression for '{}'"
              .format(file_path))
        return
    if not keep_compressed:
        os.remove(file_path)


def decompress_files(local_file_list, keep_original=False):
    """
    Decompresses list of files, and deletes compressed
    copies unless <keep_original> is True.

    """
    for f in local_file_list:
        extract_file(f, keep_original)


def fmt_timestamp(time_string):
    """
    Parses the timestamp string from an XML document
    of the form "Thu Feb 27 16:38:54 PST 2014"
    and returns a string of the form "2014".

    """
    # Remove platform-dependent timezone substring
    # of the general form "xxT"
    tz_pattern = re.compile("\s[A-Z]{3}\s")
    time_string = tz_pattern.sub(" ", time_string)

    # Get the desired time info
    time_info = time.strptime(time_string, "%a %b %d %H:%M:%S %Y")
    # year = str(time_info.tm_year)
    return time_info


def print_data(data, org_name, display=True):
    """
    Prints info from dictionary data in a specific format.
    Returns a dict with url information for every file
    in desired categories, as well as a dict with md5 information for 
    each file (keyed by file URL).

    """
    print("\nQUERY RESULTS FOR '{}'\n".format(org_name))
    dict_to_get = {}
    url_to_validate = {}
    for query_cat, v in sorted(iter(data.items()),
                               key=lambda k_v: k_v[1]["catID"]):
        print_list = []
        if not v["results"]:
            continue
        catID = v["catID"]
        dict_to_get[catID] = {}
        print_list.append(" {}: {} ".format(catID, query_cat).center(80, "="))
        results = v["results"]
        for sub_cat, items in sorted(iter(results.items()),
                                     key=lambda sub_cat_items:
                                     (sub_cat_items[0], sub_cat_items[1])):
            print_list.append("{}:".format(sub_cat))
            for index, i in sorted(items.items()):
                url = i["url"]
                dict_to_get[catID][index] = url
                if url not in url_to_validate: url_to_validate[url] = {}
                if "md5" in i:
                    url_to_validate[url]['md5'] = i["md5"]
                elif "sizeInBytes" in i:
                    url_to_validate[url]['sizeInBytes'] = int(i["sizeInBytes"])
                else:
                    print(f"warn: no md5 or sizeInBytes, so the downloaded file maybe not intact for {org_name}.")
                print_index = " {}:[{}] ".format(str(catID), str(index))
                date = fmt_timestamp(i["timestamp"])
                date_string = '{:02d}/{}'.format(date.tm_mon, date.tm_year)
                size_date = "[{}|{}]".format(i["size"], date_string)
                filename = i["filename"]
                margin = 80 - (len(size_date) + len(print_index))
                file_info = filename.ljust(margin, "-")
                print_list.append("".join([print_index, file_info, size_date]))
        if display is True:
            print('\n'.join(print_list))
            print()  # padding

    return dict_to_get, url_to_validate


def get_user_choice():
    """
    Get user file selection choice(s)

    """
    choice = input(
        "Enter file selection ('q' to quit, "
        "'usage' to review syntax, 'a' for all, "
        "'r' for regex-based filename matching):\n> ")
    if choice == "usage":
        print()
        print(select_blurb)
        print()
        return get_user_choice()
    elif choice.lower() in ("q", "quit", "exit"):
        remove_temp = input("Remove index file? (y/n): ")
        remove_temp = remove_temp.lower() in ('y', 'yes', '')
        clean_exit(remove_temp=remove_temp)
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
            clean_exit("FATAL ERROR: can't parse desired input\n?-->'{}'"
                      .format(p))
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
                    start, stop = list(map(int, i.split("-")))
                except:
                    clean_exit("FATAL ERROR: can't parse desired "
                              "input\n?-->'{}'".format(i))
                add_range = list(range(start, stop + 1))
                for e in add_range:
                    cat_list.append(e)
    return selections


def url_format_checker(u):
    """
    Checks the URL string and corrects it to the JGI Genome
    Portal format in cases where it is differently formatted,
    e.g. links listed in Phytozome.

    Such malformed links are prepended with a string which breaks
    normal parsing, for example:
    "/ext-api/downloads/get_tape_file?blocking=true&url=" is
    prepended to the standard Genome Portal URL format for (all?)
    Phytozome links and needs to be removed for cURL to use it.

    """
    if "url=" in u:
        u = u.split("url=")[-1]  # take the bit after the prepended string
    return u


def get_org_name(xml_file):
    """
    Checks an XML file for organism name information,
    for cases where an XML file is used without organism
    information supplied by the user. Returns None if
    no organism name is found.

    XML entry format is: <organismDownloads name="org_name">

    """
    name_pattern = r"name=\"(.+)\""
    org_line = None
    with open(xml_file) as f:
        for l in f:
            if "organismDownloads" in l:  # standardized name indicator
                org_line = l.strip()
                break  # don't keep looking, already found
    try:
        org_name = re.search(name_pattern, org_line).group(1)
        return org_name
    except TypeError:  # org_line still None
        return None


def is_xml(filename):
    """
    Uses hex code at the beginning of a file to try to determine if it's an
    XML file or not. This seems to be occasionally necessary; if pulling
    files from JGI tape archives, the server may error out and provide an
    XML error document instead of the intended file. This function should
    return False on all downloaded files, although false positives have not
    been thoroughly investigated.

    Adapted from http://stackoverflow.com/a/13044946/3076552

    """
    xml_hex = "\x3c"  # hex code at beginning of XML files
    read_length = len(xml_hex)
    with open(filename) as f:
        try:
            file_start = f.read(read_length)
        except UnicodeDecodeError:  # compressed files
            return False
        if file_start.startswith(xml_hex):  # XML file
            return True
        else:  # hopefully all other file types
            return False


def hidden_xml_check(file_list):
    """
    Checks a file list for any files that are actually XML error files,
    but which were intended to be of another format. Returns a list of
    all files not failing the test.

    """
    for f in list(file_list):  # iterate over copy
        if is_xml(f):
            if not f.lower().endswith("xml"):  # not recognized properly
                print("ERROR: '{}' appears to be malformed and will be left "
                      "unmodified.".format(f))
                file_list.remove(f)  # don't try to process downstream
    return file_list


def byte_convert(byte_size):
    """
    Converts a number of bytes to a more human-readable
    format.

    """
    # Calculate and display total size of selected data
    adjusted = byte_size / (1024 * 1024)  # bytes to MB
    if adjusted < 1:
        adjusted = byte_size / 1024
        unit = "KB"
    elif adjusted < 1024:
        unit = "MB"
    else:
        adjusted /= 1024
        unit = "GB"
    size_string = "{:.2f} {}".format(adjusted, unit)
    return size_string


def is_broken(filename, min_size_bytes=20, md5_hash=None, sizeInBytes=None):
    """
    Rudimentary check to see if a file appears to be broken.
    
    """
    if (
        not os.path.isfile(filename) or
        os.path.getsize(filename) < min_size_bytes or 
        (is_xml(filename) and not filename.lower().endswith('xml') or
        not check_md5(filename, md5_hash) or not check_sizeInBytes(filename, sizeInBytes))
    ):
        return True
    else:
        return False


def get_md5(*fns, buffer_size=65536):
    hash = md5()
    for fn in fns:
        with open(fn, 'rb') as f:
            while True:
                data = f.read(buffer_size)
                if not data:
                    break
                hash.update(data)

    return hash.hexdigest()

def get_sizeInBytes(filename):
    try:
        file_sizeInBytes = os.path.getsize(filename)
    except:
        file_sizeInBytes = 0

    return file_sizeInBytes

def check_md5(filename, md5_hash, print_message=True):
    if not md5_hash:
        message = "INFO: No MD5 hash listed for {}; skipping check".format(filename)
        ret_val = True
    else:
        file_md5 = get_md5(filename)
        if file_md5 == md5_hash:
            message = (
                "SUCCESS: MD5 hashes match for {} ({})".format(filename, md5_hash))
            ret_val = True
        else:
            message = ("ERROR: MD5 hash mismatch for {} (local: {}, remote: {})"
                    .format(filename, file_md5, md5_hash))
            ret_val = False
    
    if print_message is True:
        print(message)
    
    return ret_val

def check_sizeInBytes(filename, sizeInBytes, print_message=True):
    if not sizeInBytes:
        message = "INFO: No sizeInBytes listed for {}; skipping check".format(filename)
        ret_val = True
    else:
        file_sizeInBytes = get_sizeInBytes(filename)
        if file_sizeInBytes == sizeInBytes:
            message = (
                "SUCCESS: sizeInBytes match for {} ({})".format(filename, sizeInBytes))
            ret_val = True
        else:
            message = ("ERROR: sizeInBytes mismatch for {} (local: {}, remote: {})"
                    .format(filename, file_sizeInBytes, sizeInBytes))
            ret_val = False
    
    if print_message is True:
        print(message)
    
    return ret_val
    

def download_from_url(url, timeout=120, retry=0, min_file_bytes=20, url_to_validate={}):
    """
    Attempts to download a file from JGI servers using cURL.

    Returns a tuple of (filename, cURL command used, success boolean)
    
    """
    success = True
    md5_hash = url_to_validate[url].get('md5', None)
    sizeInBytes = url_to_validate[url].get('sizeInBytes', None)

    url = url.replace('&amp;', '&')

    filename = re.search('.+/(.+$)', url).group(1)
    url_prefix = "https://genome.jgi.doe.gov"
    download_command = (
        "curl -m {} '{}{}' -b cookies "
        "> {}".format(timeout, url_prefix, url, filename)
    )
    if not is_broken(filename, md5_hash=md5_hash, sizeInBytes=sizeInBytes):
        success = True
        print("Skipping existing file {}".format(filename))
    else:
        print("Downloading '{}' using command:\n{}"
            .format(filename, download_command))
        # The next line doesn't appear to be needed to refresh the cookies.
        #    subprocess.call(login, shell=True)
        status = subprocess.run(download_command, shell=True).returncode
        if status != 0 or is_broken(filename, min_file_bytes, md5_hash=md5_hash, sizeInBytes=sizeInBytes):
            success = False
            if retry > 0:
                # success = False
                # this may be needed if initial download fails
                alt_cmd = download_command.replace(
                    'blocking=true', 'blocking=false')
                current_retry = 1
                while current_retry <= retry:
                    if current_retry % 2 == 1:
                        retry_cmd = alt_cmd
                    else:
                        retry_cmd = download_command
                    print(
                        "Trying '{}' again due to download error ({}/{}):\n{}"
                        .format(filename, current_retry, retry, retry_cmd)
                    )
                    status = subprocess.run(retry_cmd, shell=True).returncode
                    if status == 0 and not is_broken(
                        filename, min_file_bytes, md5_hash=md5_hash, sizeInBytes=sizeInBytes
                    ):
                        success = True
                        break
                    current_retry += 1
                    time.sleep(10)   

    return filename, download_command, success


def get_regex():
    """
    Get regex pattern from user, compile and return.
    
    """
    #TODO make this exit gracefully if user can't
    # manage to get a working regex
    compile_success = False
    while compile_success is False:
        pattern = input('Regex pattern: ')
        try:
            pattern = re.compile(pattern)
            compile_success = True
        except:
            print('[!] ERROR: Regex pattern failed to compile.')

    return re.compile(pattern)


def retry_from_failed(login_cmd, fail_log, timeout=120, retries=3):
    """
    Try to download from URLs in a previously-generated log file.
    
    """
    organism = os.path.basename(fail_log).split('.')[0]
    fail_log = open(fail_log, 'r')
    url_list = fail_log.read().splitlines()
    try:  # fails if unable to contact server
        subprocess.check_output(login_cmd, shell=True)
    except subprocess.CalledProcessError as error:
        clean_exit("Couldn't connect with server. Please check Internet "
                  "connection and retry.")
    downloaded, failed = download_list(url_list)

    print('Finished downloading {} files'.format(len(downloaded)))
    if failed:
        log_failed(organism, failed)
    
    return downloaded, failed


def log_failed(organism, failed_urls):
    """
    Write failed URLs to a local log file.
    
    """
    fail_log = '{}.failed.log'.format(organism)
    print(
        '{} failed downloads logged to {}'.format(len(failed_urls), fail_log))
    # write failed URLs to local file
    with open(fail_log, 'w') as f:
        f.write('\n'.join(failed_urls))


def download_list(url_list, url_to_validate={}, timeout=120, retries=3):
    """
    Attempts download command on a list of partial file
    URLs (completed by download_from_url()).

    Returns a list of successfully-downloaded files and a
    list of unsuccessful URLs
    
    """
    # Run curl commands to retrieve selected files
    # Make sure the URL formats conforms to the Genome Portal format
        
    downloaded_files = []
    broken_urls = []
    subprocess.run(LOGIN_STRING, shell=True)
    start_time = time.time()
    for url in url_list:
        current_time = time.time()
        # refresh the session cookie every 5 minutes
        if current_time - start_time > 300:
            subprocess.run(LOGIN_STRING, shell=True)
            start_time = time.time()
        fn, cmd, success = download_from_url(
            url, timeout=timeout, retry=retries, url_to_validate=url_to_validate)
        if not success:
            broken_urls.append(url)
        else:
            downloaded_files.append(fn)
    
    return downloaded_files, broken_urls

# /FUNCTIONS

# BLURBS

usage_example_blurb = """\
This script will retrieve files from JGI using the cURL api. It will
return a list of possible files for downloading.

* This script depends upon cURL - it can be downloaded here:
http://curl.haxx.se/

# USAGE ///////////////////////////////////////////////////////////////////////

$ jgi-query.py [<jgi_address>, <jgi_abbreviation>] [[-xml [<your_xml>]], -f]

To get <jgi_address>, go to: http://genome.jgi.doe.gov/ and search for your
species of interest. Click through until you are at the "Info" page. For
\x1B[3mNematostella vectensis\x1B[23m, the appropriate page is
"http://genome.jgi.doe.gov/Nemve1/Nemve1.info.html".

To query using only the name simply requires the specific JGI organism
abbreviation, as referenced in the full url.

For the above example, the proper input syntax for this script would be:

$ jgi-query.py http://genome.jgi.doe.gov/Nemve1/Nemve1.info.html

                         -or-

$ jgi-query.py Nemve1

If you already have the XML file for the query in the directory, you may use
the --xml flag to avoid redownloading it (particularly useful if querying
large, top-level groups with many sub-species, such as "fungi"):

$ jgi-query.py --xml <your_xml_index>

If the XML filename is omitted when using the --xml flag, it is assumed that
the XML file is named '<jgi_abbreviation>_jgi_index.xml'. In such cases, the
organism name is required.

# /USAGE //////////////////////////////////////////////////////////////////////
"""

long_blurb = """
# USAGE ///////////////////////////////////////////////////////////////////////

# Select one or more of the following to download, using the
# following format:
#     <category number>:<indices>;<category number>:<indices>;...

# <indices> may be a mixture of comma-separated values and hyphen-
# separated ranges.

# For example, consider the following results:

====================== [1]: All models, Filtered and Not =======================
Genes:
 [1] Nemve1.AllModels.gff.gz----------------------------------------[20 MB|2012]
Proteins:
 [2] proteins.Nemve1AllModels.fasta.gz------------------------------[29 MB|2012]
Transcripts:
 [3] transcripts.Nemve1AllModels.fasta.gz---------------------------[55 MB|2012]

================================== [2]: Files ==================================
Additional Files:
 [1] N.vectensis_ABAV.modified.scflds.p2g.gz-----------------------[261 KB|2012]
 [2] Nemve1.FilteredModels1.txt.gz-----------------------------------[2 MB|2012]
 [3] Nemve1.fasta.gz------------------------------------------------[81 MB|2005]
---

# To retrieve items 1 and 2 from 'All models, Filtered and Not' and item 3 from
# 'Files', the appropriate query would be: '1:1,2;2:3'

# /USAGE //////////////////////////////////////////////////////////////////////
"""

select_blurb = """
# SYNTAX //////////////////////////////////////////////////////////////////////

Select one or more of the following to download, using the following format:

    <category number>:<i>[,<i>, <i>];<category number>:<i>-<i>;...

Indices (<i>) may be a mixture of comma-separated values and hyphen-
separated ranges.

Example: '3:4,5; 7:1-10,13' will select elements 4 and 5 from category 3, and
1-10 plus 13 from category 7.

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
                         "is the correct abbreviation. The full URL may also "
                         "be used for this argument")
parser.add_argument("-x", "--xml", nargs='?', const=1,
                    help="specify a local xml file for the query instead of "
                         "retrieving a new copy from JGI")
parser.add_argument("-c", "--configure", action='store_true',
                    help="initiate configuration dialog to overwrite existing "
                         "user/password configuration")
parser.add_argument("-s", "--syntax_help", action='store_true')
parser.add_argument("-f", "--filter_files", action='store_true',
                    help="filter organism results by config categories instead "
                         "of reporting all files listed by JGI for the query "
                         "(work in progress)")
parser.add_argument("-u", "--usage", action='store_true',
                    help="print verbose usage information and exit")
parser.add_argument("-n", "--retry_n", type=int, default=4,
                    help=("number of times to retry downloading files with "
                    "errors (0 to skip such files)"))
parser.add_argument(
    "-l", "--load_failed", type=str, metavar='logfile',
    help="retry downloading from URLs listed in log file")
parser.add_argument(
    "-r", 
    "--regex",
    type=re.compile,  # convert to regex object
    help='Regex pattern to use to auto-select and download '
    'files (no interactive prompt)')
parser.add_argument(
    "-a",
    "--all",
    action="store_true",
    help='Auto-select and download all files for query (no interactive prompt)'
)

# /ARG PARSER

# Check arguments and exit if too short
if len(sys.argv) == 1:
    parser.print_help()
    sys.exit(1)

args = parser.parse_args()
DIRECT_REGEX = args.regex
GET_ALL = args.all
if GET_ALL or DIRECT_REGEX:
    INTERACTIVE = False
else:
    INTERACTIVE = True

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

# Old syntax
# LOGIN_STRING = ("curl https://signon.jgi.doe.gov/signon/create --data-ascii "
#                 "login={}\&password={} -b cookies -c cookies > "
#                 "/dev/null".format(USER, PASSWORD))

# New syntax
LOGIN_STRING = (
    # "curl 'https://signon-old.jgi.doe.gov/signon/create' "
    "curl 'https://signon.jgi.doe.gov/signon/create' "
    "--data-urlencode 'login={}' "
    "--data-urlencode 'password={}' "
    "-s "  # suppress status output
    "-c cookies > /dev/null"
    .format(USER, PASSWORD)
    )

LOCAL_XML = False

if args.load_failed:
    logfile = args.load_failed
    print("Reading URLs from \'{}\'".format(logfile))
    retry_from_failed(LOGIN_STRING, logfile)
    clean_exit("All files in log attempted.")

# Get organism name for query
org_input = args.organism_abbreviation
if not org_input:
    if args.configure:
        sys.exit("Configuration complete. Script may now be used to query JGI. "
                 "Exiting now.")
    elif args.xml and args.xml != 1:
        # Use org_input because is already checked further down
        # and avoids re-writing this whole block
        org_input = get_org_name(args.xml)
        if not org_input:
            sys.exit("No organism specified. Exiting now.")
    else:
        sys.exit("No organism specified. Exiting now.")
org_regex = re.compile(r'\.jgi.+\.(?:gov|org).*\/(.+)\/(?!\/)')
try:  # see if it's in address form
    # organism = re.search("\.jgi.+\.(?:gov|org)/(.+)/", org_input).group(1)
    organism = org_regex.search(org_input).group(1)
except AttributeError:  # not in address form, assume string is organism name
    organism = org_input

# URL where remote XML file should be, if it exists
org_url = ("https://genome.jgi.doe.gov/portal/ext-api/downloads/get-directory?"
           "organism={}".format(organism))

# Get xml index of files, using existing local file or curl API
if args.xml:
    LOCAL_XML = True  # global referenced by clean_exit()
    xml_arg = args.xml
    if xml_arg == 1:  # --xml flag used without argument
        xml_index_filename = "{}_jgi_index.xml".format(organism)
    else:
        xml_index_filename = xml_arg
    print(
        'Retrieving information from JGI for query '
        '\'{}\' using local file \'{}\'\n'.format(organism, xml_index_filename))
else:  # fetch XML file from JGI
    xml_index_filename = "{}_jgi_index.xml".format(organism)

    # Old syntax
    # xml_address = ("curl {} -b cookies -c cookies > {}"
    #                .format(org_url, xml_index_filename))

    # New syntax
    xml_address = ("curl '{}' -L -b cookies > {}"
                   .format(org_url, xml_index_filename))
    try:  # fails if unable to contact server
        subprocess.check_output(LOGIN_STRING, shell=True)
    except subprocess.CalledProcessError as error:
        clean_exit("Couldn't connect with server. Please check Internet "
                  "connection and retry.")
    print(
        'Retrieving information from JGI for query \'{}\' using command '
        '\'{}\'\n'.format(organism, xml_address))
    subprocess.run(xml_address, shell=True)
    print()  # padding


# Parse xml file for content to download
xml_root = None
if os.path.getsize(xml_index_filename) == 0:  # happens if user and/or pw wrong
    clean_exit("Invalid username/password combination (or other issue).\n"
              "Restart script with flag '-c' to reconfigure credentials.")
try:
    xml_in = ET.ElementTree(file=xml_index_filename)
    xml_root = xml_in.getroot()
except ET.ParseError:  # organism not found/xml file contains errors
    clean_exit("Cannot parse XML file or no organism match found.\n"
              "Ensure remote file exists and has content at the "
              "following address:\n{}".format(org_url))


# Get categories from config (including possible user additions)
# Will only be used if --filter_files flag
DESIRED_CATEGORIES = config_info["categories"]


# Choose between different XML parsers
# if args.filter_files, user wants only those files in <desired_categories>
file_list = get_file_list(xml_index_filename, filter_categories=args.filter_files)


# Check if file has any categories of interest
if not any(v["results"] for v in list(file_list.values())):
    print(("ERROR: no results found for '{}' in any of the following "
           "categories:\n---\n{}\n---"
           .format(organism, "\n".join(DESIRED_CATEGORIES))))
    clean_exit()


# Decision tree depending on if non-interactive options given
regex_filter = None
user_choice = None
display_info = True
if GET_ALL:
    user_choice = 'a'
    display_info = False
elif DIRECT_REGEX:
    user_choice = 'r'
    regex_filter = DIRECT_REGEX
    display_info = False

url_dict, url_to_validate = print_data(file_list, organism, display=display_info)

if not user_choice:
    # Ask user which files to download from xml
    user_choice = get_user_choice()
    if user_choice == 'r':
        regex_filter = get_regex()

urls_to_get = set()

# special case for downloading all available files
# or filtering with a regular expression
if user_choice in ('a', 'r'):
    for k, v in sorted(url_dict.items()):
        for u in v.values():
            if regex_filter:
                fn = re.search('.+/([^\/]+$)', u).group(1)
                match = regex_filter.search(fn)
                if not match:
                    continue
            urls_to_get.add(u)
else:
    # Retrieve user-selected file urls from dict
    ids_dict = parse_selection(user_choice)
    for k, v in sorted(ids_dict.items()):
        for i in v:
            urls_to_get.add(url_dict[k][i])


# Calculate and display total size of selected data
urls_to_get = sorted(urls_to_get)
filenames = [u.split('/')[-1] for u in urls_to_get]
file_sizes = get_sizes(file_list, sizes_by_url={})
total_size = sum([file_sizes[url] for url in urls_to_get])
size_string = byte_convert(total_size)
num_files = len(urls_to_get)
print(("Total download size for {} files: {}".format(num_files, size_string)))
if INTERACTIVE:
    download = input("Continue? (y/n/[p]review files): ").lower()
    if download == "p":
        while download == "p":
            print('\n'.join(filenames))
            download = input("Continue with download? (y/n/[p]review files): ").lower()
    if download != "y":
        clean_exit("ABORTING DOWNLOAD")

downloaded_files, failed_urls = download_list(
    urls_to_get, url_to_validate=url_to_validate, retries=args.retry_n)

print("Finished downloading {} files.".format(len(downloaded_files)))

if failed_urls and INTERACTIVE:
    n_broken = len(failed_urls)
    retry_broken = input(
        "{} files failed to download; retry them? (y/n): ".format(n_broken))
    if retry_broken.lower() in ('yes', 'y'):
        downloaded_files, failed_urls = download_list(
            failed_urls, url_to_validate=url_to_validate, retries=1)

if failed_urls:
    log_failed(organism, failed_urls)

# Kindly offer to unpack files, if files remain after error check
if downloaded_files and INTERACTIVE:
    decompress = input(("Decompress all downloaded files? "
                        "(y/n/k=decompress and keep original): "))
    if decompress != "n":
        if decompress == "k":
            keep_original = True
        else:
            keep_original = False
        decompress_files(downloaded_files, keep_original)
        print('Finished decompressing all files.')

# Clean up and exit
# "cookies" file is always created
if INTERACTIVE:
    keep_temp = input("Keep temporary files ('{}' and 'cookies')? (y/n): "
                    .format(xml_index_filename))
    if keep_temp.lower() not in "y, yes":
        clean_exit()
    else:
        print("Leaving temporary files intact and exiting.")
else:
    clean_exit()

sys.exit(0)
