# jgi-query
A command-line tool for querying and downloading from the [Joint Genome Institute (JGI)](http://genome.jgi-psf.org/) online database. Useful for accessing JGI data from command-line-only resources such as remote servers, or as a lightweight alternative to JGI's other [GUI-based download tools](http://genome.jgi-psf.org/help/download.jsf).

### Dependencies

- A [user account with JGI](http://contacts.jgi-psf.org/registration/new) (free)
- [cURL](http://curl.haxx.se/), required by the JGI download API
- [Python](https://www.python.org/downloads/) 3.x (current development) or 2.7.x (deprecated but provided -- now *significantly outdated*)

### Installation

1. Download `jgi-query.py`
2. Ensure that you're running the correct version of Python with `python --version`. If this reports Python 2.x, run the script using `python3` instead of `python`
3. From the command line, run the script with the command `python jgi-query.py` to show usage information and further instructions

#### Usage information

```shell
usage: jgi-query.py [-h] [-x [XML]] [-c] [-s] [-f] [-u] [-n RETRY_N]
                    [-l logfile] [-r REGEX] [-a]
                    [organism_abbreviation]

This script will list and retrieve files from JGI using the curl API. It will
return a list of all files available for download for a given query organism.

positional arguments:
  organism_abbreviation
                        organism name formatted per JGI's abbreviation. For
                        example, 'Nematostella vectensis' is abbreviated by
                        JGI as 'Nemve1'. The appropriate abbreviation may be
                        found by searching for the organism on JGI; the name
                        used in the URL of the 'Info' page for that organism
                        is the correct abbreviation. The full URL may also be
                        used for this argument (default: None)

optional arguments:
  -h, --help            show this help message and exit
  -x [XML], --xml [XML]
                        specify a local xml file for the query instead of
                        retrieving a new copy from JGI (default: None)
  -c, --configure       initiate configuration dialog to overwrite existing
                        user/password configuration (default: False)
  -s, --syntax_help
  -f, --filter_files    filter organism results by config categories instead
                        of reporting all files listed by JGI for the query
                        (work in progress) (default: False)
  -u, --usage           print verbose usage information and exit (default:
                        False)
  -n RETRY_N, --retry_n RETRY_N
                        number of times to retry downloading files with errors
                        (0 to skip such files) (default: 4)
  -l logfile, --load_failed logfile
                        retry downloading from URLs listed in log file
                        (default: None)
  -r REGEX, --regex REGEX
                        Regex pattern to use to auto-select and download files
                        (no interactive prompt) (default: None)
  -a, --all             Auto-select and download all files for query (no
                        interactive prompt) (default: False)
```

### Author's note

This is a somewhat better-commented (emphasis on "somewhat") version of a script I wrote for grabbing various datasets using a headless Linux server. For a lot of my lab's bioinformatics work, we don't store/manipulate data on our local computers, and I was not able to find a good tool that allowed for convenient queries of the JGI database without additional software.

JGI also no longer allows simple downloading of many of their datasets (via `wget`, for example), which is another reason behind the creation of this script.

I highly encourage anyone with more advanced Python skills (read: almost everyone) to fork and submit pull requests.

### General overview

JGI uses a [cURL-based API](https://docs.google.com/document/d/1UXovE52y1ab8dZVa-LYNJtgUVgK55nHSQR3HQEJJ5-A/view) to provide information/download links to files in their database.

In brief, `jgi-query` begins by using cURL to grab an XML file for the query text. The XML file describes all of the available files and their parent categories. For example, the file for *Aureobasidium subglaciale* (JGI abbreviation "Aurpu_var_sub1") begins:

![Aurpu_var_sub1_xml_example](http://i.imgur.com/4nImnxx.png)

`jgi-query` will parse the XML file to find entries with a `filename` attribute and, depending on command-line arguments, a parent category from the list of categories in `jgi-query.config`. It then displays the available files with minimal metadata, and prompts the user to enter their selection.

### File selection

Main file categories in the report are numbered, as are files within each category. The selection syntax is `category_number`:`file_selection`, where `file_selection` is either a comma-separated list (e.g. `file1`, `file2`) or a contiguous range (e.g. `file1`-`file4`). For multiple parent categories and associated files, category/file list groupings are linked with semicolons (e.g. `category1`:`file1`,`file2`;`category2`:`file5`-`file8`).

### Bulk file downloading

Additionally, there is a regex-based file selection option (enter "r" at the file selection prompt) which may be useful for selecting a large number of related files (see the [Python regex documentation](https://docs.python.org/3/library/re.html#re-syntax) for syntax information). For example, to retrieve all files with "AllModels" in their names, the regex to enter at the regex prompt would be `.*AllModels.*`.

### Use in a larger pipeline

For programmatic use, `jgi-query` also has command-line arguments, `-a` and `-r`, that allow retrieval of either complete or regex-filtered datasets, respectively, while bypassing interactive prompts. For example, to retrieve all gzipped GFF3 files with "FilteredModels1" for _Schizophyllum commune_:

`python3 jgi-query.py Schco3 -r 'FilteredModels1.*\.gff3\.gz$'`

### Sample output for _Nematostella vectensis_ ('Nemve1')

```shell
➜ python3 jgi-query.py Nemve1                                  
Retrieving information from JGI for query 'Nemve1' using command 'curl 'https://genome.jgi.doe.gov/ext-api/downloads/get-directory?organism=Nemve1' -L -b cookies > Nemve1_jgi_index.xml'

  % Total    % Received % Xferd  Average Speed   Time    Time     Time  Current
                                 Dload  Upload   Total   Spent    Left  Speed
100   379  100   379    0     0   1857      0 --:--:-- --:--:-- --:--:--  1857
100  4350    0  4350    0     0   3958      0 --:--:--  0:00:01 --:--:-- 4248k


QUERY RESULTS FOR 'Nemve1'

======================= 1: All models, Filtered and Not ========================
Genes:
 1:[1] Nemve1.AllModels.gff.gz-----------------------------------[20 MB|03/2012]
Proteins:
 1:[2] proteins.Nemve1AllModels.fasta.gz-------------------------[29 MB|03/2012]
Transcripts:
 1:[3] transcripts.Nemve1AllModels.fasta.gz----------------------[55 MB|03/2012]

=================================== 2: Files ===================================
Additional Files:
 2:[1] N.vectensis_ABAV.modified.scflds.p2g.gz------------------[261 KB|03/2012]
 2:[2] Nemve1.FilteredModels1.txt.gz------------------------------[2 MB|03/2012]
 2:[3] Nemve1.fasta.gz-------------------------------------------[81 MB|10/2005]
 2:[4] Nemve_JGIest.fasta.gz-------------------------------------[30 MB|03/2012]
 2:[5] Nemve_JGIestCL.fasta.gz------------------------------------[8 MB|03/2012]
 2:[6] NvTRjug.fasta.gz-------------------------------------------[4 KB|03/2012]

========================= 3: Filtered Models ("best") ==========================
Genes:
 3:[1] Nemve1.FilteredModels1.gff.gz------------------------------[3 MB|03/2012]
 3:[2] Nvectensis_19_PAC2_0.GFF3.gz-------------------------------[2 MB|03/2012]
Proteins:
 3:[3] proteins.Nemve1FilteredModels1.fasta.gz--------------------[5 MB|03/2012]
Transcripts:
 3:[4] transcripts.Nemve1FilteredModels1.fasta.gz-----------------[8 MB|03/2012]

Enter file selection ('q' to quit, 'usage' to review syntax, 'a' for all, 'r' for regex-based filename matching):
> 2:3;3:1
Total download size for 2 files: 84.02 MB
Continue? (y/n/[p]review files): y
Downloading 'Nemve1.FilteredModels1.gff.gz' using command:
curl -m 120 'https://genome.jgi.doe.gov/portal/Nemve1/download/Nemve1.FilteredModels1.gff.gz' -b cookies > Nemve1.FilteredModels1.gff.gz
  % Total    % Received % Xferd  Average Speed   Time    Time     Time  Current
                                 Dload  Upload   Total   Spent    Left  Speed
100 3078k  100 3078k    0     0  4918k      0 --:--:-- --:--:-- --:--:-- 4918k
Downloading 'Nemve1.fasta.gz' using command:
curl -m 120 'https://genome.jgi.doe.gov/portal/Nemve1/download/Nemve1.fasta.gz' -b cookies > Nemve1.fasta.gz
  % Total    % Received % Xferd  Average Speed   Time    Time     Time  Current
                                 Dload  Upload   Total   Spent    Left  Speed
100 81.0M  100 81.0M    0     0  5320k      0  0:00:15  0:00:15 --:--:-- 2881k
Finished downloading 2 files.
Decompress all downloaded files? (y/n/k=decompress and keep original): y
Finished decompressing all files.
Keep temporary files ('Nemve1_jgi_index.xml' and 'cookies')? (y/n): n
Removing temp files and exiting

~ took 1m 17s 
➜ 
```