#!/usr/bin/env python# PYTHON_ARGCOMPLETE_OK

#### IMPORTS
import argcomplete, argparse, datetime, re, sys, os, logging, traceback # itertools
from collections import namedtuple

# #with os.add_dll_directory('C:/blp/DAPI/blpapi_cpp_3.23.2.1/lib'):
import blpapi


#### DIAGNOSTICS LOGGING (passive; does not change CLI/output)
# A new log file is created on every run. Logging failures never break execution.
_LOG_TS = datetime.datetime.now(datetime.UTC).strftime("%Y%m%d_%H%M%S")
_LOG_PID = os.getpid()
_LOG_DIR = os.path.dirname(__file__) if "__file__" in globals() else os.getcwd()
LOG_FILE = os.path.join(_LOG_DIR, f"drone_{_LOG_TS}_{_LOG_PID}.log")

try:
    logging.basicConfig(
        filename=LOG_FILE,
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
except Exception:
    # Logging must never break the script.
    pass

def log_info(msg):
    try:
        logging.info(msg)
    except Exception:
        pass

def log_error(msg):
    try:
        logging.error(msg)
    except Exception:
        pass

def log_exception(prefix):
    try:
        logging.error("%s\n%s", prefix, traceback.format_exc())
    except Exception:
        pass



#### SERVICES
INSTRUMENT_SERVICE = "//blp/instruments"
APIFLDS_SERVICE = "//blp/apiflds"
REFDATA_SERVICE = "//blp/refdata"
SERVICE_NAME = blpapi.Name("serviceName")

#### REQUESTS
INSTRUMENT_LIST_REQUEST = "instrumentListRequest"
CURVE_LIST_REQUEST = "curveListRequest"
GOVT_LIST_REQUEST = "govtListRequest"
FIELD_INFO_REQUEST = "FieldInfoRequest" # full list request filtered by type (All, Static, RealTime)
FIELD_LIST_REQUEST = "FieldListRequest" # description of the requested field
FIELD_SEARCH_REQUEST = "FieldSearchRequest" # search for a specific field by field mnemonic
CATEGORIZED_FIELD_SEARCH_REQUEST = "CategorizedFieldSearchRequest" # search by category
REFERENCE_DATA_REQUEST = "ReferenceDataRequest"
HISTORICAL_DATA_REQUEST = "HistoricalDataRequest"
HIBAR_DATA_REQUEST = "IntradayBarRequest"
HITICK_DATA_REQUEST = "IntradayTickRequest"

##### COMMON NAMES
REQUEST_FAILURE = blpapi.Name("RequestFailure")
SESSION_TERMINATED = blpapi.Name("SessionTerminated")
SESSION_STARTUP_FAILURE = blpapi.Name("SessionStartupFailure")
SERVICE_OPEN_FAILURE = blpapi.Name("ServiceOpenFailure")
ERROR_RESPONSE = blpapi.Name("ErrorResponse")
ERROR_INFO = blpapi.Name("errorInfo")
RESPONSE_ERROR = blpapi.Name("responseError")
REASON = blpapi.Name("reason")
MESSAGE = blpapi.Name("message")

#### UTILS
# error print
def eprint(*args, **kwargs):
    # Preserve existing stderr output, but also log for post-mortem analysis.
    try:
        msg = " ".join(str(a) for a in args)
        log_error(msg)
    except Exception:
        pass
    print(*args, file=sys.stderr, **kwargs)

# default dates
def defaultDates(minutes, days=None):
    dt = datetime.datetime.now()
    if days is not None:
        df = dt - datetime.timedelta(days=days)
    else:
        df = dt - datetime.timedelta(minutes=minutes)

    return [df, dt]

# date validators
def valid_eod_date(s):
    try:
        return datetime.datetime.strptime(s, "%Y-%m-%d")
    except ValueError:
        msg = "not a valid date: {0!r}".format(s)
        raise argparse.ArgumentTypeError(msg)

def valid_oth_date(s):
    try:
        return datetime.datetime.strptime(s, "%Y-%m-%dT%H:%M:%S")
    except ValueError:
        msg = "not a valid date: {0!r}".format(s)
        raise argparse.ArgumentTypeError(msg)

# date parser    
def parseDate(value):
    return datetime.datetime.strptime(value, "%Y-%m-%d")

# datetime parse
def parseDatetime(value):
    return datetime.datetime.strptime(value, "%Y-%m-%dT%H:%M:%S")

# generate days sequence for historical data
def workdays(d, end, excluded=(6, 7)):
    days = []
    while d.date() <= end.date():
        if d.isoweekday() not in excluded:
            days.append(d.strftime("%Y-%m-%d"))
        d += datetime.timedelta(days=1)
    return days        

# for speed
def alldays(d, end):
    days = []
    while d.date() <= end.date():
        days.append(d.strftime("%Y-%m-%d"))
        d += datetime.timedelta(days=1)
    return days        

# find multiple indices in a list (vs .index())
def find_indices(a_list, item_to_find):
    indices = []
    for idx, value in enumerate(a_list):
        if value == item_to_find:
            indices.append(idx)
    return indices

# mock completer for security completion tests
def get_securities(prefix, parsed_args, **kwargs):
        return ['ES1 Index', 'VG1 Index', 'GX1 Index', 'IB1 Index', 'RX1 Comdty', 'TY1 Comdty', 'GC1 Comdty', 'DU1 Comdty', 'ZB3 Comdty']

#### ACTIONS FOR PARSER
# parse overrides (fieldId=value) in args
class OverridesAction(argparse.Action):
    """The action that parses overrides options from user input"""
    Override = namedtuple("Override", ["fieldId", "value"])

    def __call__(self, parser, args, values, option_string=None):
        vals = values.split("=", 1)
        overrides = getattr(args, self.dest)
        overrides.append(Override(vals[0], vals[1]))

# comma-delimited list for args
class MultiAction(argparse.Action):
    """The action that parses comma-delimited list from user input"""
    def __call__(self, parser, args, values, option_string=None):
        vals = values.split(",")
        content = getattr(args, self.dest)
        for i in vals:
            content.append(i.strip())

# comma-separated date_from, date_to, with defaults
class MultiDate(argparse.Action):
    """The action that parses comma-delimited date list from user input"""
    def __call__(self, parser, args, values, option_string=None):
        vals = values.split(",", 1)
        content = getattr(args, self.dest)
        for i in vals:
            if valid_eod_date(i.strip()):
                content.append(i.strip())
            else:
                eprint(f"wrong format for {i.strip()}")
        if len(content) == 0:
            dates = defaultDates(minutes=0, days=10)
            content.append(dates[0].strftime("%Y-%m-%d"))
            content.append(dates[1].strftime("%Y-%m-%d"))
        if len(content) == 1:
            dates = defaultDates(0, days=10)
            content.append(dates[1].strftime("%Y-%m-%d"))

# comma-separated datetime_from, datetime_to, with defaults
class MultiDateTime(argparse.Action):
    """The action that parses comma-delimited date list from user input"""
    def __call__(self, parser, args, values, option_string=None):
        vals = values.split(",", 1)
        content = getattr(args, self.dest)
        for i in vals:
            if valid_oth_date(i.strip()):
                content.append(i.strip())
            else:
                eprint(f"wrong format for {i.strip()}")
        if len(content) == 0:
            dates = defaultDates(minutes=5)
            content.append(dates[0].strftime("%Y-%m-%dT%H:%M:%S"))
            content.append(dates[1].strftime("%Y-%m-%dT%H:%M:%S"))
        if len(content) == 1:
            dates = defaultDates(minutes=5)
            content.append(dates[1].strftime("%Y-%m-%dT%H:%M:%S"))

# parse host            
class HostAction(argparse.Action):
    """The action that parses host options from user input"""
    def __call__(self, parser, args, values, option_string=None):
        vals = values.split(":", 1)
        if len(vals) != 2:
            parser.error(f"Invalid host option '{values}'")

        hosts = getattr(args, self.dest)
        hosts.append((vals[0], int(vals[1])))

#### MAIN PARSER    
def parseCmdLine():
        """New drone parser with autocomplete features"""
        # the display can be formatted via formatter_class
        parser = argparse.ArgumentParser(
                prog = 'drone',
                description = 'requesting Bloomberg data',
                usage = './drone [-h]',
                epilog = 'Have fun!',
                add_help = False,
        )

        # connections / server options
        parser.add_argument("-H", "--host", dest="hosts",
                           help="server name or IP (default: 127.0.0.1:8194). Can be specified multiple times.",
                           metavar="host:port", action=HostAction, default=[])

        # debug
        parser.add_argument("-d", "--debug", dest="debug", action="store_true")

        # parsers and subparsers
        subparsers = parser.add_subparsers(title='subrequests', dest='reqType', description='list of sub requests available')

        # tickers
        ticker = subparsers.add_parser('ticker', help='ticker search help')
        ticker.add_argument("-u", "--universe", dest="requestType",
                choices=[ "instrument", "curve", "govt" ],
                help="specify the universe (default: %(default)s)", metavar="universe [instrument, curve, govt]", default="instrument")        
        ticker.add_argument("-i", "--ids", dest="query", type=str, help="search ticker / security", metavar="security")
        ticker.add_argument("--limit", dest="maxResults", help="max results returned (default: %(default)d)", metavar="limit", type=int, default=10)

        # fields
        field = subparsers.add_parser('field', help='field search help')
        field.add_argument("-t", "--type", dest="requestType",
                choices=[ "search", "info", "list", "catsearch" ],
                help="specify the search type (default: %(default)s)", metavar="type [search, info, list, catsearch]", default="search")
        field.add_argument("-f", "--fld", dest="query", default="PX_LAST", type=str,
                           help="search field (default: %(default)s)", metavar="field")        
        field.add_argument("--doc", action="store_true", help="get an HTML documentation")
        field.add_argument("--limit", dest="maxResults", help="max results returned (default: %(default)d)", metavar="limit", type=int, default=1000)

        # master
        master = subparsers.add_parser('master', help='master request help')
        master.add_argument("-i", "--ids", dest="securities", help="Security to request. Can be specified multiple times.",
            metavar="security", action=MultiAction, default=[])
        master.add_argument("-f", "--field", dest="fields", help="Field to request. Can be specified multiple times.",
            metavar="field", action=MultiAction, default=[])
        master.add_argument("-o", "--override", dest="overrides", help="Field to override. Can be specified multiple times.",
            metavar="<fieldId>=<value>", action=OverridesAction, default=[])

        # histo
        histo = subparsers.add_parser('histo', help='historical request help')
        subhisto = histo.add_subparsers(title='historical', dest="subHisto", description='list of historical sub requests available')

        # histo EOD
        eod = subhisto.add_parser('eod', help='historical EOD request help')
        eod.add_argument("-i", "--ids", dest="securities", help="Security to request. Can be specified multiple times.",
                            metavar="security", action=MultiAction, default=[])
        eod.add_argument("-f", "--field", dest="fields", help="Field to request. Can be specified multiple times.",
                            metavar="field", action=MultiAction, default=[])
        eod.add_argument('-d', '--date', '--dates', dest="dates", action=MultiDate, default=[], help='date from, date to, yyyy-mm-dd format')
        eod.add_argument('--curr', type=str, dest="currency", default=None, help='currency of denomination')
        eod.add_argument('--locf', action='store_true', default=False, help='last observation carried forward (default %(default)s)')
        eod.add_argument('--weekend', action='store_true', default=False, help='include weekend (default %(default)s)')
        eod.add_argument('--to-db', dest="todb", action='store_true', default=False, help='print in database format (default %(default)s)')

        # histo ticks
        ticks = subhisto.add_parser('ticks', help='historical ticks request help')

        ticks.add_argument("-i", "--ids", dest="securities", help="Security to request. Can be specified multiple times.",
                            metavar="security", action=MultiAction, default=[])
        ticks.add_argument("-f", "--field", dest="fields", help="Field to request. Can be specified multiple times.",
                            metavar="field [TRADE, BID, ASK, BEST_BID, BEST_ASK, MID_PRICE, AT_TRADE]",choices=['TRADE', 'BID', 'ASK', 'BID_BEST', 'BEST_BID', 'ASK_BEST', 'BEST_ASK', 'MID_PRICE', 'AT_TRADE'], action=MultiAction, default=[])
        ticks.add_argument('-d', '--date', '--dates', dest="dates", action=MultiDateTime, default=[], help='date from, date to, yyyy-mm-ddThh:mm:ss format')

        # histo bars
        bars = subhisto.add_parser('bars', help='historical bars request help')
        bars.add_argument("-i", "--ids", dest="securities", help="Security to request. Can be specified multiple times.",
                            metavar="security", action=MultiAction, default=[])
        bars.add_argument("-f", "--field", dest="fields", help="Field to request. Can be specified multiple times.",
                            metavar="field [TRADE, BID, ASK]",choices=['TRADE', 'BID', 'ASK'], action=MultiAction, default=[])
        bars.add_argument("-s", "--size", dest="barInterval", type=int, default=1, help="Bar interval in minutes (default: %(default)d)", metavar="barInterval")
        bars.add_argument('-d', '--date', '--dates', dest="dates", action=MultiDateTime, default=[], help='date from, date to, yyyy-mm-ddThh:mm:ss format')
        bars.add_argument("-G", "--gap-fill-initial-bar", dest="gapFillInitialBar", help="Gap fill initial bar", action="store_true", default=False)

        # TODO: real-time if needed

        # help
        parser.add_argument('-?', '-h', '--help', action='help', help='show this help message and exit')

        argcomplete.autocomplete(parser)
        options = parser.parse_args()

        return options

#### COMMON REQUESTS & RESULTS NAMES
ID = blpapi.Name("id")
DATE = blpapi.Name("date")
ROW = blpapi.Name("row")
VALUE = blpapi.Name("value")

MNEMONIC = blpapi.Name("mnemonic")
DESCRIPTION = blpapi.Name("description")
DOCUMENTATION = blpapi.Name("documentation")
OVRDS = blpapi.Name("overrides")
OVERRIDES = OVRDS  # backward/forward compatibility
FIELD_ID = blpapi.Name("fieldId")

NAME_RESULTS = blpapi.Name("results")
NAME_DESCRIPTION = blpapi.Name("description")

CATEGORY = blpapi.Name("category")
CATEGORY_NAME = blpapi.Name("categoryName")

# SECURITIES & FIELDS
SECURITIES = blpapi.Name("securities")
SECURITY_DATA = blpapi.Name("securityData")
SECURITY = blpapi.Name("security")
SECURITY_ERROR = blpapi.Name("securityError")

FIELDS = blpapi.Name("fields")
FIELD_TYPE = blpapi.Name("fieldType")
FIELD_DATA = blpapi.Name("fieldData")
FIELD_INFO = blpapi.Name("fieldInfo")
FIELD_EXCEPTIONS = blpapi.Name("fieldExceptions")
FIELD_ERROR = blpapi.Name("fieldError")
FIELD_SEARCH_ERROR = blpapi.Name("fieldSearchError")

# HISTORICAL DATA
TIME = blpapi.Name("time")
START_DATE = blpapi.Name("startDate")
END_DATE = blpapi.Name("endDate")
START_DATE_TIME = blpapi.Name("startDateTime")
END_DATE_TIME = blpapi.Name("endDateTime")

#### THEMATIC REQUESTS
def createTickerRequest(service, serviceType, options):
    """Instruments Request"""
    request = service.createRequest(serviceType)
    request[blpapi.Name("query")] = options.query
    request[blpapi.Name("maxResults")] = options.maxResults

    options.reqId = request.getRequestId()

    return request

def createFieldsRequest(service, serviceType, options):
    """Fields Request"""
    SEARCH_SPEC = blpapi.Name("searchSpec")
    RETURN_FIELD_DOC = blpapi.Name("returnFieldDocumentation")

    request = service.createRequest(serviceType)

    if serviceType == CATEGORIZED_FIELD_SEARCH_REQUEST:
        request.set(SEARCH_SPEC, options.query)
    elif serviceType == FIELD_INFO_REQUEST:
        idElement = request.getElement(ID)
        idElement.appendValue(options.query) # idElement.appendValue("MID")
    elif serviceType == FIELD_LIST_REQUEST:
        request[FIELD_TYPE] = "All" # to change Other options are Static and RealTime
    elif serviceType == FIELD_SEARCH_REQUEST:
        request.set(SEARCH_SPEC, options.query)

    # exclude = request.getElement(blpapi.Name("exclude")) # exclude.setElement(FIELD_TYPE, "Static")
    request.set(RETURN_FIELD_DOC, options.doc)
    options.reqId = request.getRequestId()

    return request

def createRefDataRequest(service, options):
    """Reference Data Request"""
    request = service.createRequest(REFERENCE_DATA_REQUEST)
    securitiesElement = request.getElement(SECURITIES)

    for security in options.securities:
        securitiesElement.appendValue(security)

    fieldsElement = request.getElement(FIELDS)
    for field in options.fields:
        fieldsElement.appendValue(field)

    # Add overrides
    if options.overrides:
        overridesElement = request.getElement(OVERRIDES)
        for override in options.overrides:
            overrideElement = overridesElement.appendElement()
            overrideElement.setElement(FIELD_ID, override.fieldId)
            overrideElement.setElement(VALUE, override.value)

    options.reqId = request.getRequestId()            

    return request

def createHiDataRequest(service, options):
    """Historical EOD Data Request"""
    request = service.createRequest(HISTORICAL_DATA_REQUEST)

    request[SECURITIES] = options.securities
    request[FIELDS] = options.fields

    request[blpapi.Name("periodicityAdjustment")] = "ACTUAL"
    request[blpapi.Name("periodicitySelection")] = "DAILY"
    request[blpapi.Name("nonTradingDayFillOption")] = "ALL_CALENDAR_DAYS"

    if options.currency is not None:
        request[blpapi.Name("currency")] = options.currency

    request[blpapi.Name("nonTradingDayFillMethod")] = "PREVIOUS_VALUE" if options.locf else "NIL_VALUE"

    request[START_DATE] = options.dates[0].replace("-","")
    request[END_DATE] = options.dates[1].replace("-","")

    options.reqId = request.getRequestId()

    return request

def createHiBarRequest(service, options):
    """Historical Bar Data Request"""
    request = service.createRequest(HIBAR_DATA_REQUEST)

    if len(options.fields) > 1:
        eprint(f"Only one field per request, processed: {options.fields[0]}")
    if len(options.securities) > 1:
        eprint(f"Only one security per request, processed: {options.securities[0]}")

    # Only one security / eventType per request
    request.set(SECURITY, options.securities[0])
    request.set(blpapi.Name("eventType"), options.fields[0])
    request.set(blpapi.Name("interval"), options.barInterval)

    request.set(START_DATE_TIME, options.dates[0])
    request.set(END_DATE_TIME, options.dates[1])

    if options.gapFillInitialBar:
        request.set(blpapi.Name("gapFillInitialBar"), options.gapFillInitialBar)

    options.reqId = request.getRequestId()

    return request

def createHiTickRequest(service, options):
    """Historical Tick Data Request"""
    request = service.createRequest(HITICK_DATA_REQUEST)

    if len(options.fields) > 1:
        eprint(f"Only one field per request, processed: {options.fields[0]}")
    if len(options.securities) > 1:
        eprint(f"Only one security per request, processed: {options.securities[0]}")

    request.set(SECURITY, options.securities[0])
    request[blpapi.Name("eventTypes")] = options.fields
    request.set(START_DATE_TIME, options.dates[0])
    request.set(END_DATE_TIME, options.dates[1])
    options.reqId = request.getRequestId()

    return request

################### TICKER CALL PROCESS RESPONSE
#### GOVT
def processResponseGovt(event, options):
    """Process Instruments Govt response"""
    NAME_PARSEKY = blpapi.Name("parseky")
    NAME_TICKER = blpapi.Name("ticker")
    NAME_NAME = blpapi.Name("name")

    for msg in event:
        if msg.getRequestId() != options.reqId:
            continue

        if msg.messageType() == ERROR_RESPONSE:
            eprint(f"Received error: {msg}")
            continue

        results = msg.getElement(NAME_RESULTS)

        for i, result in enumerate(results):
            parsekey = result[NAME_PARSEKY]
            name = result[NAME_NAME].replace(";", ", ")
            ticker = result[NAME_TICKER]
            print(f"{parsekey};{name};{ticker}")

###### CURVE
def processResponseCurve(event, options):
    """Process Instruments Curve response"""

    NAME_CURVE = blpapi.Name("curve")
    CURVE_RESPONSE_ELEMENTS = [ blpapi.Name("country"), blpapi.Name("currency"), blpapi.Name("curveid"), blpapi.Name("publisher"), blpapi.Name("bbgid") ]
    CURVE_TYPE = blpapi.Name("type")
    CURVE_SUBT = blpapi.Name("subtype")

    for msg in event:
        if msg.getRequestId() != options.reqId:
            continue

        if msg.messageType() == ERROR_RESPONSE:
            eprint(f"Received error: {msg}")
            continue

        results = msg[NAME_RESULTS]

        for i, result in enumerate(results):
            elements_values = [
                    f"{result[n]}" for n in CURVE_RESPONSE_ELEMENTS
            ]

            curve_type = result[CURVE_TYPE][0]
            curve_subtype = result[CURVE_SUBT][0]
            curve = result[NAME_CURVE]
            description = result[NAME_DESCRIPTION].replace(";", ", ")
            print(f"{curve};{description};{';'.join(elements_values)};{curve_type};{curve_subtype}")

#### INSTRUMENT
def repl_func(m):
    """process regular expression match groups for word upper-casing problem"""
    return m.group(1) + m.group(2).upper()

def processResponseInst(event, options):
    """Process generic Instruments response"""
    NAME_SECURITY = blpapi.Name("security")

    for msg in event:
        if msg.getRequestId() != options.reqId:
            continue

        if msg.messageType() == ERROR_RESPONSE:
            eprint(f"Received error: {msg}")
            continue

        results = msg[NAME_RESULTS]

        for i, result in enumerate(results):
            security = result[NAME_SECURITY] # re.sub("(\s)(\S)", repl_func, result[NAME_SECURITY].replace("<"," ").replace(">",""))
            description = result[NAME_DESCRIPTION].replace(";", ", ")
            print(f"{security};{description}")

################### FIELDS CALL PROCESS RESPONSE
#### HELPERS            
def printField(field):
    """Print Fields helper"""
    fieldId = field[ID]
    if FIELD_INFO in field:
        fieldInfo = field[FIELD_INFO]
        fieldMnemonic = fieldInfo[MNEMONIC]
        fieldDesc = fieldInfo[DESCRIPTION]

        category = ','.join([ cat for cat in fieldInfo[CATEGORY_NAME] ]) if fieldInfo.hasElement(CATEGORY_NAME) else ""
        overrides = ','.join([ ovrd for ovrd in fieldInfo[OVRDS] ]) if fieldInfo.hasElement(OVRDS) else ""
        doc = ";" + fieldInfo[DOCUMENTATION].replace(';', ',').replace('\n', '<br />') if fieldInfo.hasElement(DOCUMENTATION) else ""

        print(f"{fieldId};{fieldMnemonic};{fieldDesc};{category};{overrides}{doc}")
    else:
        errorMsg = field[FIELD_ERROR][MESSAGE]
        eprint(f"ERROR: {fieldId} - {errorMsg}")

def printCatField(field, cat, desc):
    """Print Fields helper"""
    fieldId = field[ID]
    if FIELD_INFO in field:
        fieldInfo = field[FIELD_INFO]
        fieldMnemonic = fieldInfo[MNEMONIC]
        fieldDesc = fieldInfo[DESCRIPTION]

        category = ','.join([ cat for cat in fieldInfo[CATEGORY_NAME] ]) if fieldInfo.hasElement(CATEGORY_NAME) else ""
        overrides = ','.join([ ovrd for ovrd in fieldInfo[OVRDS] ]) if fieldInfo.hasElement(OVRDS) else ""
        doc = ";" + fieldInfo[DOCUMENTATION].replace(';', ',').replace('\n', '<br />') if fieldInfo.hasElement(DOCUMENTATION) else ""

        print(f"{fieldId};{fieldMnemonic};{fieldDesc};{category};{overrides};{cat};{desc}{doc}")
    else:
        errorMsg = field[FIELD_ERROR][MESSAGE]
        eprint(f"ERROR: {fieldId} - {errorMsg}")

def processResponseCatFields(event, options):
    """Process categorized Fields response"""
    for msg in event:
        if msg.getRequestId() != options.reqId:
            continue

        if FIELD_SEARCH_ERROR in msg:
            eprint(msg)
            continue

        categories = msg[CATEGORY]
        for category in categories:
            category_name = category[CATEGORY_NAME].replace(';', ',')
            category_desc = category[DESCRIPTION].replace(';', ',')

            fields = category[FIELD_DATA]
            for field in fields:
                if options.cnt < options.maxResults:
                    printCatField(field, category_name, category_desc)
                    options.cnt += 1
                else:
                    sys.exit(0)

def processResponseListFields(event, options):
    """Process list Fields response"""
    for msg in event:
        if msg.getRequestId() != options.reqId:
            continue

        fields = msg.getElement(FIELD_DATA)
        for i in range(fields.numValues()):
            if options.cnt < options.maxResults:
                printField(fields.getValueAsElement(i))
                options.cnt += 1
            else:
                sys.exit(0)

def processResponseFields(event, options):
    """Process generic Fields response"""
    for msg in event:
        if msg.getRequestId() != options.reqId:
            continue

        fields = msg[FIELD_DATA]
        for field in fields:
            if options.cnt < options.maxResults:
                printField(field)
                options.cnt += 1

########### MASTER DATA PROCESS RESPONSE
def processMasterResponseEvent(event, options):
    """Process Master response"""
    ids = options.securities
    flds = options.fields
    res = {}

    for msg in event:
        if msg.getRequestId() != options.reqId:
            continue

        if msg.hasElement(RESPONSE_ERROR):
            eprint(f"REQUEST FAILED: {msg.getElement(RESPONSE_ERROR)}")
            continue

        securities = msg.getElement(SECURITY_DATA)
        numSecurities = securities.numValues()

        for i in range(numSecurities):
            security = securities.getValueAsElement(i)
            ticker = security.getElementAsString(SECURITY)

            ln = f"{ticker}"

            if security.hasElement(FIELD_DATA):
                fields = security.getElement(FIELD_DATA)
                if fields.numElements() > 0:

                    for fld in flds:
                        if fields.hasElement(fld):
                            ln += f";{fields.getElementAsString(fld)}"
                        else:
                            ln += ";NA"

                    res[ticker] = ln
    return res

########### HISTORICAL EOD DATA PROCESS RESPONSE
def processHiEODResponseEvent(event, options):
    """Process Historical response"""
    ids, flds = options.securities, options.fields
    nf, nc = len(flds), len(ids) * len(flds)

    if options.todb:    
        for msg in event:
            if msg.getRequestId() != options.reqId:
                continue

            if msg.hasElement(RESPONSE_ERROR):
                eprint(f"REQUEST FAILED: {msg.getElement(RESPONSE_ERROR)}")
                continue

            block = msg.getElement(SECURITY_DATA)
            security = block.getElementAsString(SECURITY)

            data = block.getElement(FIELD_DATA)
            numData = data.numValues()

            for i in range(numData):
                val = data.getValueAsElement(i)
                date = val.getElementAsString(DATE)
                for fld in flds:
                    if val.hasElement(fld):
                        print(f"{date};{security};{fld};{val.getElementAsString(fld)}")
                    else:
                        print(f"{date};{security};{fld};NA")
    else:

        for msg in event:
            if msg.getRequestId() != options.reqId:
                continue

            if msg.hasElement(RESPONSE_ERROR):
                eprint(f"REQUEST FAILED: {msg.getElement(RESPONSE_ERROR)}")
                continue

            block = msg.getElement(SECURITY_DATA)
            security = block.getElementAsString(SECURITY)

            js = find_indices(ids, security)

            data = block.getElement(FIELD_DATA)
            numData = data.numValues()

            for k in range(numData):
                val = data.getValueAsElement(k)
                date = val.getElementAsString(DATE)

                for l in range(len(flds)):
                    if val.hasElement(flds[l]):
                        for j in js:
                            options.res[date][j*nf+l] = val.getElementAsString(flds[l])

    return options.res

########### HISTORICAL BAR DATA PROCESS RESPONSE
def processHiBarResponseEvent(event, options):    
    """Process Historical Bars response"""

    BAR_DATA = blpapi.Name("barData")
    BAR_TICK_DATA = blpapi.Name("barTickData")
    OPEN, HIGH, LOW, CLOSE, VOLUME = blpapi.Name("open"), blpapi.Name("high"), blpapi.Name("low"), blpapi.Name("close"), blpapi.Name("volume")
    NUM_EVENTS = blpapi.Name("numEvents")

    security = options.securities[0]
    res = {}

    for msg in event:
        if msg.getRequestId() != options.reqId:
            continue

        if msg.hasElement(RESPONSE_ERROR):
            eprint(f"REQUEST FAILED: {msg.getElement(RESPONSE_ERROR)}")
            continue

        data = msg.getElement(BAR_DATA)
        bars = data.getElement(BAR_TICK_DATA)
        for bar in bars:
            bTime = bar.getElementAsString(TIME)
            bOpen = bar.getElementAsString(OPEN)
            bHigh = bar.getElementAsString(HIGH)            
            bLow  = bar.getElementAsString(LOW)
            bClose = bar.getElementAsString(CLOSE)
            nEvents = bar.getElementAsString(NUM_EVENTS)
            volume = bar.getElementAsString(VOLUME)
            print(f"{bTime};{security};{bOpen};{bHigh};{bLow};{bClose};{nEvents};{volume}")

    return res

########### HISTORICAL TICK DATA PROCESS RESPONSE
def processHiTickResponseEvent(event, options):
    """Process Historical Ticks response"""
    # TICKS
    TICK_DATA = blpapi.Name("tickData")
    SIZE, TYPE = blpapi.Name("size"), blpapi.Name("type")

    security = options.securities[0]
    res = {}

    for msg in event:
        if msg.getRequestId() != options.reqId:
            continue

        if msg.hasElement(RESPONSE_ERROR):
            eprint(f"REQUEST FAILED: {msg.getElement(RESPONSE_ERROR)}")
            continue

        data = msg.getElement(TICK_DATA)
        ticks = data.getElement(TICK_DATA)
        for tick in ticks:
            tTime = tick.getElementAsString(TIME)
            tType = tick.getElementAsString(TYPE)
            tValue = tick.getElementAsString(VALUE)
            tSize = tick.getElementAsString(SIZE)

            print(f"{tTime};{security};{tType};{tValue};{tSize}")

    return res

################### GENERIC REQUEST SEND
def sendRequest(options, session):
    """Sends a request based on the request type."""    
    requestType = options.requestType

    # headers are managed here
    if requestType in [ "instrument", "curve", "govt" ]:

        if requestType == "instrument":
            uni = INSTRUMENT_LIST_REQUEST
            print("SECURITY;DESC")

        elif requestType == "curve":
            uni = CURVE_LIST_REQUEST
            print("CURVE;DESC;COUNTRY;CRNCY;CURVE_ID;PUBLISHER;BBGID;TYPE;SUBTYPE")

        elif requestType == "govt":
            uni = GOVT_LIST_REQUEST
            print("ID;NAME;TICKER");

        instrumentsService = session.getService(INSTRUMENT_SERVICE)
        request = createTickerRequest(instrumentsService, uni, options)

    elif requestType in [ "search", "info", "list", "catsearch" ]:
        add = ";DOCUMENTATION" if options.doc else ""
        options.cnt = 0

        if requestType == "search":
            uni = FIELD_SEARCH_REQUEST
            print(f"ID;MNEM;DESC;CATEGORIES;OVERRIDES{add}")
        elif requestType == "info":
            uni = FIELD_INFO_REQUEST
            print(f"ID;MNEM;DESC;CATEGORIES;OVERRIDES{add}")
        elif requestType == "list":
            uni = FIELD_LIST_REQUEST
            print(f"ID;MNEM;DESC;CATEGORIES;OVERRIDES{add}")
        elif requestType == "catsearch":
            uni = CATEGORIZED_FIELD_SEARCH_REQUEST
            print(f"ID;MNEM;DESC;CATEGORIES;OVERRIDES;CAT;CAT_DESC{add}")

        fieldsService = session.getService(APIFLDS_SERVICE)
        request = createFieldsRequest(fieldsService, uni, options)

    elif requestType == REFERENCE_DATA_REQUEST:
        hdr = "ID"
        for fld in options.fields:
            hdr += f";{fld}"
        print(hdr)            
        refDataService = session.getService(REFDATA_SERVICE)
        request = createRefDataRequest(refDataService, options)

    elif requestType == HISTORICAL_DATA_REQUEST:
        if options.todb:
            hdr = "TIMESTAMP;ID;FIELD;VALUE"
        else:
            hdr = "TIMESTAMP"
            for id in options.securities:
                for fld in options.fields:
                    hdr += f";{id}_{fld}"
        print(hdr)        
        refDataService = session.getService(REFDATA_SERVICE)
        request = createHiDataRequest(refDataService, options)

    elif requestType == HIBAR_DATA_REQUEST:
        print(f"TIME;SECURITY;OPEN;HIGH;LOW;CLOSE;NUM_EVENTS;VOLUME")
        refDataService = session.getService(REFDATA_SERVICE)
        request = createHiBarRequest(refDataService, options)

    elif requestType == HITICK_DATA_REQUEST:
        print("TIME;SECURITY;FIELD;VALUE;SIZE")
        refDataService = session.getService(REFDATA_SERVICE)
        request = createHiTickRequest(refDataService, options)

    session.sendRequest(request)

################### GENERIC EVENT/RESPONSE LOOP PROCESSING
def waitForResponse(session, options):
    """Waits for response after sending the request"""
    res = {}

    requestType = options.requestType
    done = False
    while not done:
        event = session.nextEvent()
        eventType = event.eventType()

        if eventType == blpapi.Event.PARTIAL_RESPONSE:
            # update is for master requests, to keep order it is required to have the whole returned dictionary
            # before it is reworked to match the initial request structure and order
            res.update(processResponseEvent(event, options))

        elif eventType == blpapi.Event.RESPONSE:
            res.update(processResponseEvent(event, options))

            if options.requestType == REFERENCE_DATA_REQUEST:
                # print master data in the right security order (not guaranteed otherwise)
                for id in options.securities:
                    print(res[id])

            if options.requestType == HISTORICAL_DATA_REQUEST:
                # print historical eod in the right order, with all the dates required
                for d in options.wkdays:
                    print(d + ';' + ';'.join(options.res[d]))

            done = True

        elif eventType == blpapi.Event.REQUEST_STATUS:
            for msg in event:
                print(msg)
                if msg.messageType == blpapi.Names.REQUEST_FAILURE:
                    reason = msg.getElement(REASON)
                    print(f"Request failed: {reason}")

                    done = True                    
                elif msg.messageType() == SESSION_TERMINATED:
                    print(f"Session terminated: {msg}")

                    done = True

def printEvent(event):
    for msg in event:
        print(f"Received response to request {msg.getRequestId()}")
        print(msg)

def processResponseEvent(event, options):
    """Processes a response to the request."""
    requestType = options.requestType
    res = {}

    if options.debug:
        printEvent(event)

    if requestType == "curve":
        processResponseCurve(event, options)
    elif requestType == "govt":
        processResponseGovt(event, options)
    elif requestType == "instrument":
        processResponseInst(event, options)
    elif requestType == "catsearch":
        processResponseCatFields(event, options)
    elif requestType == "list":
        processResponseListFields(event, options)
    elif requestType in [ "info", "search" ]:
        processResponseFields(event, options)
    elif requestType == REFERENCE_DATA_REQUEST:
        res.update(processMasterResponseEvent(event, options))
    elif requestType == HISTORICAL_DATA_REQUEST:
        processHiEODResponseEvent(event, options)
    elif requestType == HIBAR_DATA_REQUEST:
        processHiBarResponseEvent(event, options)
    elif requestType == HITICK_DATA_REQUEST:
        processHiTickResponseEvent(event, options)
    else:
        printEvent(event)

    return res

def getData(serviceName, options):
    """get data from service"""
    sessionOptions = blpapi.SessionOptions()
    # sessionOptions.setServerHost("127.0.0.1")
    # sessionOptions.setServerPort(8194)

    session = blpapi.Session(sessionOptions)
    try:
        if not session.start():
            print("Failed to start session.")
            return

        if not session.openService(serviceName):
            print(f"Failed to open {serviceName}")
            return

        sendRequest(options, session)
        waitForResponse(session, options)
    finally:
        session.stop()

def main():
    log_info(f"START argv={sys.argv} cwd={os.getcwd()} log={LOG_FILE}")
    """Main function"""
    options = parseCmdLine()

    res = {}
    options.res = res

    # print(options)
    if options.reqType == "master":
        options.requestType = REFERENCE_DATA_REQUEST

        # default values
        if len(options.securities) == 0:
            options.securities = ["ES1 Index"]
        if len(options.fields) == 0:
            options.fields = ["PX_LAST"]

        getData(REFDATA_SERVICE, options)

    elif options.reqType == "ticker":
        getData(INSTRUMENT_SERVICE, options)

    elif options.reqType == "field":
        if len(options.query) == 0:
            options.query = ["PX_LAST"]

        getData(APIFLDS_SERVICE, options)

    elif options.reqType == "histo":

        # default values
        if len(options.securities) == 0:
            options.securities = ["ES1 Index"]

        if len(options.fields) == 0:
            options.fields = ["PX_LAST"] if options.subHisto == "eod" else ["TRADE"]

        if options.subHisto == "eod":
            options.requestType = HISTORICAL_DATA_REQUEST            

            if not options.dates:
                dates = defaultDates(minutes=0, days=10)
                options.dates = list(map(lambda x: x.strftime("%Y-%m-%d"), dates))

            dfrom = datetime.datetime.strptime(options.dates[0], "%Y-%m-%d")
            dto = datetime.datetime.strptime(options.dates[1], "%Y-%m-%d")

            if not options.todb:
                # manage print days
                days = alldays(dfrom, dto) if options.weekend else workdays(dfrom, dto)

                # create the initial list
                res, nc = {}, len(options.securities) * len(options.fields)

                for d in days:
                    res[d] = ['NA'] * nc

                options.res = res
                options.wkdays = days
            else:
                options.wkdays = []

        elif options.subHisto == "bars":
            options.requestType = HIBAR_DATA_REQUEST
            if not options.dates:
                dates = defaultDates(minutes=60)
                options.dates = list(map(lambda x: x.strftime("%Y-%m-%dT%H:%M:%S"), dates))

        elif options.subHisto == "ticks":
            options.requestType = HITICK_DATA_REQUEST
            if not options.dates:
                dates = defaultDates(minutes=5)
                options.dates = list(map(lambda x: x.strftime("%Y-%m-%dT%H:%M:%S"), dates))

        getData(REFDATA_SERVICE, options)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # pylint: disable=broad-except
        log_exception("Unhandled exception")
        print(e)

# flat_list = itertools.chain(*([]+[x.split(',') for x in args.ids]))
# print(list(flat_list))
