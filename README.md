# jgi-query
A command-line tool for querying and downloading from the [Joint Genome Institute (JGI)](http://genome.jgi-psf.org/) online database. Useful for accessing JGI data from command-line-only resources such as remote servers, or as a lightweight alternative to JGI's other [GUI-based download tools](http://genome.jgi-psf.org/help/download.jsf).

### Dependencies
- A [user account with JGI](http://contacts.jgi-psf.org/registration/new) (free)
- [cURL](http://curl.haxx.se/), required by the JGI download API
- [Python](https://www.python.org/downloads/) 3.x (current development) or 2.7.x (deprecated but provided)

### Installation
1. Download `jgi-query.py`
2. Ensure that you're running the correct version of Python with `python --version`. If this reports Python 2.x, run the script using `python3` instead of `python`
3. From the command line, run the script with the command `python jgi-query.py` to show usage information and further instructions

### Author notes
This is a somewhat better-commented (emphasis on "somewhat") version of a script I wrote for grabbing various datasets using a headless Linux server. For a lot of my lab's bioinformatics work, we don't store/manipulate data on our local computers, and I was not able to find a good tool that allowed for convenient queries of the JGI database without additional software.

JGI also no longer allows simple downloading of many of their datasets (via `wget`, for example), which is another reason behind the creation of this script.

I highly encourage anyone with more advanced Python skills (read: almost everyone) to fork and submit pull requests, and hope that someone else finds it useful.

### General overview
JGI uses a [cURL-based API](https://docs.google.com/document/d/1UXovE52y1ab8dZVa-LYNJtgUVgK55nHSQR3HQEJJ5-A/view) to provide information/download links to files in their database.

In brief, `jgi-query.py` begins by using cURL to grab an XML file for the query text. The XML file describes all of the available files and their parent categories. For example, the file for *Aureobasidium subglaciale* (JGI abbreviation "Aurpu_var_sub1") begins:

![Aurpu_var_sub1_xml_example](http://i.imgur.com/4nImnxx.png)

`jgi-query.py` will parse the XML file to find entries with a `filename` attribute and, depending on command-line arguments, a parent category from the list of categories in `jgi-query.config`. It then displays the available files with minimal metadata, and prompts the user to enter their selection.

Main file categories in the report are numbered, as are files within each category. The selection syntax is `category_number`:`file_selection`, where `file_selection` is either a comma-separated list (e.g. `file1`, `file2`) or a contiguous range (e.g. `file1`-`file4`). For multiple parent categories and associated files, category/file list groupings are linked with semicolons (e.g. `category1`:`file1`,`file2`;`category2`:`file5`-`file8`).

### Sample output for _Nematostella vectensis_ (JGI abbreviation 'Nemve1')
```bash
glarue@glarue-XPS-13 ~/Documents/Coding/Python/Research/jgi-query $ jgi-query.py Nemve1

# USAGE ///////////////////////////////////////////////////////////////////////

# Select one or more of the following to download, using the
# following format:
#     <category number>:<indices>;<category number>:<indices>;...

# Indices may be a mixture of comma-separated values and hyphen-
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


  % Total    % Received % Xferd  Average Speed   Time    Time     Time  Current
                                 Dload  Upload   Total   Spent    Left  Speed
100   197    0   152  100    45    337    100 --:--:-- --:--:-- --:--:--   451
  % Total    % Received % Xferd  Average Speed   Time    Time     Time  Current
                                 Dload  Upload   Total   Spent    Left  Speed
100  4012    0  4012    0     0   8048      0 --:--:-- --:--:-- --:--:--  8778

QUERY RESULTS FOR 'Nemve1'

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
 [4] Nemve_JGIest.fasta.gz------------------------------------------[30 MB|2012]
 [5] Nemve_JGIestCL.fasta.gz-----------------------------------------[8 MB|2012]
 [6] NvTRjug.fasta.gz------------------------------------------------[4 KB|2012]

======================== [3]: Filtered Models ("best") =========================
Genes:
 [1] Nemve1.FilteredModels1.gff.gz-----------------------------------[3 MB|2012]
 [2] Nvectensis_19_PAC2_0.GFF3.gz------------------------------------[2 MB|2012]
Proteins:
 [3] proteins.Nemve1FilteredModels1.fasta.gz-------------------------[5 MB|2012]
Transcripts:
 [4] transcripts.Nemve1FilteredModels1.fasta.gz----------------------[8 MB|2012]

Enter file selection ('q' to quit, 'usage' to review syntax):
>2:5;3:1
Total download size of selected files: 11.23 MB
Continue? (y/n): y
Downloading 'Nemve_JGIestCL.fasta.gz'

  % Total    % Received % Xferd  Average Speed   Time    Time     Time  Current
                                 Dload  Upload   Total   Spent    Left  Speed
100 8421k  100 8421k    0     0  1850k      0  0:00:04  0:00:04 --:--:-- 1978k
Downloading 'Nemve1.FilteredModels1.gff.gz'

  % Total    % Received % Xferd  Average Speed   Time    Time     Time  Current
                                 Dload  Upload   Total   Spent    Left  Speed
100 3078k  100 3078k    0     0  1047k      0  0:00:02  0:00:02 --:--:-- 1059k
Finished downloading all files.
Decompress all downloaded files? (y/n/k=decompress and keep original): y
Finished decompressing all files.
Keep temporary files ('Nemve1_jgi_index.xml' and 'cookies')? (y/n): n
Removing temp files and exiting
glarue@glarue-XPS-13 ~/Documents/Coding/Python/Research/jgi-query $
```

