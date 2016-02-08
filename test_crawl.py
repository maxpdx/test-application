from __future__ import division
import scrapy
from twisted.internet import reactor, defer
from scrapy.settings import Settings
from scrapy.crawler import CrawlerRunner
from scrapy.crawler import Crawler
from scrapy.utils.log import configure_logging
from scrapy.spiders import CrawlSpider, Rule
from scrapy.selector import HtmlXPathSelector
from scrapy.linkextractors import LinkExtractor
import filecmp
import os
from os.path import join, getsize


# ================================ ENUMS ======================================
# A handy enum for the tests tuple used below
SPIDER = 0
SETTING = 1

# Default cache directory
HTTPCACHE_DIR = '.scrapy/'

# Handy shorthands for long backend names
DEFAULT = 'scrapy.extensions.httpcache.FilesystemCacheStorage'
DELTA = 'scrapy.extensions.httpcache.DeltaLeveldbCacheStorage'
# =============================== END ENUMS ===================================


# =============================== DATA STRUCTURES =============================
# The list of spiders to run. Each item is 2-tuple with the first
# item being the spider to run and the second being the settings
# object with wich to run it
tests = []

# The list of test results that should be compared against each other
# Each item in the list is a dictionary with the following structure:
#     spider_name  -> the name of the spider (i.e. xkcd)
#     file_default -> the name of the html file generated by the default
#                     cache backend
#     file_delta   -> the name of the html file generated by the delta backend
#     dir_default  -> the directory the where the cache for the default backend
#                     is located
#     dir_delta    -> the directory where the cache for the delta backend is
comparisons = []

# A dictionary storing the results of a test run in the following format:
# 'isCorrect'   -> True/False  true if the html files are the same,
#                              false otherwise
# 'd1_size'     -> num         the size of the uncompressed directory
# 'd2_size'     -> num         the size of the compressed directory
# 'size_result' -> num         the percent size difference
results = []
# ============================ END DATA STRUCTURES ============================


# ============================ UTILITY FUNCTIONS ==============================
# ============================ get_new_settings() =============================
#  A utility function to set a series of Settings parameters to avoid
# some code reduplication/boiler plate lameness. It always sets the Settings
# object's HTTPCACHE_ENABLED to True. This is done in "functional style"
# (rather than mutate a passed in Settings object, we just pass back a newly
# created one)
# Parameters:
#   directory: Directory to output cache to
#   backend: Cache backend to use
# Returns: Settings
def get_new_settings(directory=HTTPCACHE_DIR,
                     backend=DEFAULT,
                     depth=1):
    s = Settings()
    s.set('HTTPCACHE_ENABLED', True)
    s.set('HTTPCACHE_DIR', directory)
    s.set('HTTPCACHE_STORAGE', backend)
    s.set('DEPTH_LIMIT', depth)
    return s


# =========================== generate_test_results() =========================
# Takes a dictionary of two test spider runs (one delta, one default)
# compares them, and returns a the results
# Parameters:
# c : A dictionary representing two test runs that must be compared against
#     each other. The dictionary has the following key -> values:
#     spider_name  -> the name of the spider (i.e. xkcd)
#     file_default -> the name of the html file generated by the default
#                     cache backend
#     file_delta   -> the name of the html file generated by the delta backend
#     dir_default  -> the directory the where the cache for the default backend
#                     is located
#     dir_delta    -> the directory where the cache for the delta backend is
# Returns:
# A dictionary in the following format:
# 'isCorrect'  : True/False  true if the html files are the same,
#                            false otherwise
# 'd1_size'    : num         the size of the uncompressed directory
# 'd2_size'    : num         the size of the compressed directory
# 'size_result': num         the percent size difference
def generate_test_results(c):
    r = {
        'name': c['spider_name'],
        'd1': HTTPCACHE_DIR + c['dir_default'],
        'd2': HTTPCACHE_DIR + c['dir_delta'],
        'd1_size': dir_size(HTTPCACHE_DIR + c['dir_default']),
        'd2_size': dir_size(HTTPCACHE_DIR + c['dir_delta'])
    }

    # Checking correctness
    file1 = os.path.isfile(c['file_default'])
    file2 = os.path.isfile(c['file_delta'])
    if file1 and file2:
        r['isCorrect'] = filecmp.cmp(c['file_default'], c['file_delta'], True)
    else:
        if not file1:
            not_found = c['file_default']
        elif not file2:
            not_found = c['file_delta']
        r['isCorrect'] = "Unable to find file to compare: '%s'" % not_found

    # Getting the difference result
    if r['d1_size'] != 0 and r['d2_size'] != 0:
        if r['d1_size'] < r['d2_size']:
            r['size_result'] = 100 - ((r['d1_size'] / r['d2_size']) * 100)
        else:
            r['size_result'] = 100 - ((r['d2_size'] / r['d1_size']) * 100)
    else:
        r['size_result'] = 0
    return r


# ============================== display_test_results =========================
# Outputs the results of a test to the screen
# Parameters:
#  r : a result dictionary (see entry under DATA STRUCTURES above)
# Returns: None
def display_test_results(r):
    print(r['name'])
    print("\tHTML files match? %s" % r['isCorrect'])
    print("\t%s bytes in %s" % (r['d1_size'], r['d1']))
    print("\t%s bytes in %s" % (r['d2_size'], r['d2']))
    print("\t%.4f%% difference" % r['size_result'])
    print("-----")


# =============================== dir_size() ==================================
# Gets the size in bytes of a directory
# Parameters:
#  start_path : the directory from which the walk should begin
# Returns:
#  the total size of all subdirectories from the start directory
def dir_size(start_path=HTTPCACHE_DIR):
    total_size = 0
    for dirpath, dirnames, filenames in os.walk(start_path):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            total_size += os.path.getsize(fp)
    return total_size


# ======================= write_response_file =================================
# Helper function that writes a response body file. It depends on the storage
# backend to which file it will write.
# Parameters:
#   self     : the spider class
#   response : from a spider
# Returns:
#   none
def write_response_file(self, response):
    if self.crawler.settings.get('HTTPCACHE_STORAGE') == DEFAULT:
        filename = self.__class__.__name__ + '_default.html'
    else:
        filename = self.__class__.__name__ + '_delta.html'
    with open(filename, 'wb') as f:
        f.write(response.body)
    return


# ========================== set_spider() =====================================
# Prepares a spider to be run by a script. Sets up scrapy settings,
# sets the source and a delta file html files.
# Parameters:
#   spider              : class     A class that is defined for the spider
#   test_list           : 2-tuple   Data structure for tests to be performed
#   comparisons_list    : 5-tuple   Data structure for comparisons to be stored
# Returns:
#   2-tuple of test_list and a comparison_list
def set_spider(spider, test_list=tests, comparisons_list=comparisons):
    # Queue one test using the default backend
    test_list.append((spider, get_new_settings(spider.__name__ + '_default')))

    # Queue another test using our backend
    test_list.append((spider,
                      get_new_settings(spider.__name__ + '_delta', DELTA)))

    # Queue up a test pair result to compare the runs of this
    comparisons_list.append({
        'spider_name': spider.__name__,
        'file_default': spider.__name__ + '_default.html',
        'file_delta': spider.__name__ + '_delta.html',
        'dir_default': spider.__name__ + '_default',
        'dir_delta': spider.__name__ + '_delta'
    })

    return test_list, comparisons_list

# ============================ END UTILITY FUNCTIONS ==========================


# ============================ SPIDERS ========================================
# A Fanfic Spider to grab some data that (hopefully) is a bad
# candidate for delta compression. Work in progress.
class FanficSpider(scrapy.spiders.CrawlSpider):
    name = "fanfic_test"
    allowed_domains = ["www.fanfiction.net"]
    start_urls = ["https://www.fanfiction.net/comic/Scott-Pilgrim/"]

    rules = (Rule(LinkExtractor(allow=()),callback="handle_page", follow=True),
             )

    def handle_page(self, response):
        write_response_file(self, response)


# XKCD Spider
class XkcdSpider(scrapy.spiders.CrawlSpider):
    name = "xkcd"
    allowed_domains = ["10.10.10.10"]
    start_urls = (
        'http://10.10.10.10',
    )

    def parse(self, response):
        write_response_file(self, response)
        self.parse_next(response)

    def parse_next(self, response):
        # Safe if Xpath is empty, extract handles it.
        prev_link = response.xpath(
                '//*[@id="middleContainer"]/ul[1]/li[2]/a/@href').extract()
        if prev_link:
            url = response.urljoin(prev_link[0])
            yield scrapy.Request(url, callback=self.parse_next)

# ================================== END SPIDERS ==============================

(tests, comparisons) = set_spider(FanficSpider)
(tests, comparisons) = set_spider(XkcdSpider)

configure_logging()
runner = CrawlerRunner()

@defer.inlineCallbacks
def crawl():
    for test in tests:
        crawler = Crawler(test[SPIDER], test[SETTING])
        yield runner.crawl(crawler)
    reactor.stop()

crawl()
reactor.run()

# After all spiders have run go ahead and conduct comparisons
results = list(map(generate_test_results, comparisons))

# Now display results of compare
print("==================== SUMMARY ========================")
for result in results:
    display_test_results(result)
