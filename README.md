# jgi-query
A command-line tool for querying and downloading from the [Joint Genome Institute (JGI)](http://genome.jgi-psf.org/) online database. Useful for accessing JGI data from command-line-only resources such as remote servers, or as a lightweight alternative to JGI's other [GUI-based download tools](http://genome.jgi-psf.org/help/download.jsf).

### Dependencies
- A [user account with JGI](http://contacts.jgi-psf.org/registration/new) (free)
- [cURL](http://curl.haxx.se/), required by the JGI download API
- [Python](https://www.python.org/downloads/) 2.7.x

### Installation
1. Download `jgi-query.py`
2. Ensure that you're running the correct version of Python with `python --version`. If this reports Python 3.x, run the script using `python2` instead of `python`
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
