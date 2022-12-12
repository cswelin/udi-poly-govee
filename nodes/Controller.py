

"""
Get the polyinterface objects we need. 
a different Python module which doesn't have the new LOG_HANDLER functionality
"""
import udi_interface
from govee_led_wez import GoveeController, GoveeDevice


# My Template Node
# from nodes import TemplateNode

"""
Some shortcuts for udi interface components

- LOGGER: to create log entries
- Custom: to access the custom data class
- ISY:    to communicate directly with the ISY (not commonly used)
"""
LOGGER = udi_interface.LOGGER
LOG_HANDLER = udi_interface.LOG_HANDLER
Custom = udi_interface.Custom
ISY = udi_interface.ISY

# IF you want a different log format than the current default
LOG_HANDLER.set_log_format('%(asctime)s %(threadName)-10s %(name)-18s %(levelname)-8s %(module)s:%(funcName)s: %(message)s')

class Controller(udi_interface.Node):
    """
    Class Methods
      query(): Queries and reports ALL drivers for ALL nodes to the ISY.
      getDriver('ST'): gets the current value from Polyglot for driver 'ST'
        returns a STRING, cast as needed
      setDriver('ST', value, report, force, uom): Updates the driver with
        the value (and possibly a new UOM)
      reportDriver('ST', force): Send the driver value to the ISY, normally
        it will only send if the value has changed, force will always send
      reportDrivers(): Send all driver values to the ISY
      status()
    """
    def __init__(self, polyglot, primary, address, name):
        """
        Optional.
        Super runs all the parent class necessities. You do NOT have
        to override the __init__ method, but if you do, you MUST call super.

        In most cases, you will want to do this for the controller node.
        """
        super(Controller, self).__init__(polyglot, primary, address, name)
        self.poly = polyglot
        self.name = 'Govee Controller'  # override what was passed in
        self.hb = 0
        self.goveeController = GoveeController()
        self.api_key = None 
        self.lan_control = False


        # Create data storage classes to hold specific data that we need
        # to interact with.  
        self.Parameters = Custom(polyglot, 'customparams')
        self.Notices = Custom(polyglot, 'notices')
        self.TypedParameters = Custom(polyglot, 'customtypedparams')
        self.TypedData = Custom(polyglot, 'customtypeddata')


        LOGGER.info('init: Parameters={}'.format(self.Parameters))
        LOGGER.info('init: TypedParameters={}'.format(self.TypedParameters))
        LOGGER.info('init: TypedData={}'.format(self.TypedData))
        # Subscribe to various events from the Interface class.  This is
        # how you will get information from Polyglog.  See the API
        # documentation for the full list of events you can subscribe to.
        #
        # The START event is unique in that you can subscribe to 
        # the start event for each node you define.

        self.poly.subscribe(self.poly.START, self.start, address)
        self.poly.subscribe(self.poly.LOGLEVEL, self.handleLevelChange)
        self.poly.subscribe(self.poly.CUSTOMPARAMS, self.parameterHandler)
        self.poly.subscribe(self.poly.CUSTOMTYPEDPARAMS, self.typedParameterHandler)
        self.poly.subscribe(self.poly.CUSTOMTYPEDDATA, self.typedDataHandler)
        self.poly.subscribe(self.poly.POLL, self.poll)

        self.controller.set_device_change_callback(self.device_changed)


        # Tell the interface we have subscribed to all the events we need.
        # Once we call ready(), the interface will start publishing data.
        self.poly.ready()

        # Tell the interface we exist.  
        self.poly.addNode(self)


    def start(self):
        """
        The Polyglot v3 Interface will publish an event to let you know you
        can start your integration. (see the START event subscribed to above)

        This is where you do your initialization / device setup.
        Polyglot v3 Interface startup done.

        Here is where you start your integration. I.E. if you need to 
        initiate communication with a device, do so here.
        """

        self.controller.start_lan_poller()
        # Send the profile files to the ISY if neccessary. The profile version
        # number will be checked and compared. If it has changed since the last
        # start, the new files will be sent.
        self.poly.updateProfile()

        # Send the default custom parameters documentation file to Polyglot
        # for display in the dashboard.
        self.poly.setCustomParamsDoc()

        # Initializing a heartbeat is an example of something you'd want
        # to do during start.  Note that it is not required to have a
        # heartbeat in your node server
        self.heartbeat(0)

        # Device discovery. Here you may query for your device(s) and 
        # their capabilities.  Also where you can create nodes that
        # represent the found device(s)
        self.discover()

        

    """
    Called via the CUSTOMPARAMS event. When the user enters or
    updates Custom Parameters via the dashboard. The full list of
    parameters will be sent to your node server via this event.

    Here we're loading them into our local storage so that we may
    use them as needed.

    New or changed parameters are marked so that you may trigger
    other actions when the user changes or adds a parameter.

    NOTE: Be carefull to not change parameters here. Changing
    parameters will result in a new event, causing an infinite loop.
    """
    def parameterHandler(self, params):
        self.Parameters.load(params)
        LOGGER.debug('Loading parameters now')
        self.check_params()

    """
    Called via the CUSTOMTYPEDPARAMS event. This event is sent When
    the Custom Typed Parameters are created.  See the check_params()
    below.  Generally, this event can be ignored.

    Here we're re-load the parameters into our local storage.
    The local storage should be considered read-only while processing
    them here as changing them will cause the event to be sent again,
    creating an infinite loop.
    """
    def typedParameterHandler(self, params):
        self.TypedParameters.load(params)
        LOGGER.debug('Loading typed parameters now')
        LOGGER.debug(params)

    """
    Called via the CUSTOMTYPEDDATA event. This event is sent when
    the user enters or updates Custom Typed Parameters via the dashboard.
    'params' will be the full list of parameters entered by the user.

    Here we're loading them into our local storage so that we may
    use them as needed.  The local storage should be considered 
    read-only while processing them here as changing them will
    cause the event to be sent again, creating an infinite loop.
    """
    def typedDataHandler(self, params):
        self.TypedData.load(params)
        LOGGER.debug('Loading typed data now')
        LOGGER.debug(params)

    """
    Called via the LOGLEVEL event.
    """
    def handleLevelChange(self, level):
        LOGGER.info('New log level: {}'.format(level))

    """
    Called via the POLL event.  The POLL event is triggerd at
    the intervals specified in the node server configuration. There
    are two separate poll events, a long poll and a short poll. Which
    one is indicated by the flag.  flag will hold the poll type either
    'longPoll' or 'shortPoll'.

    Use this if you want your node server to do something at fixed
    intervals.
    """
    def poll(self, flag):
        if 'longPoll' in flag:
            LOGGER.debug('longPoll (controller)')
            self.heartbeat()
        else:
            LOGGER.debug('shortPoll (controller)')

    def query(self,command=None):
        """
        Optional.

        The query method will be called when the ISY attempts to query the
        status of the node directly.  You can do one of two things here.
        You can send the values currently held by Polyglot back to the
        ISY by calling reportDriver() or you can actually query the 
        device represented by the node and report back the current 
        status.
        """
        nodes = self.poly.getNodes()
        for node in nodes:
            nodes[node].reportDrivers()

    def discover(self, *args, **kwargs):
        """
        Example
        Do discovery here. Does not have to be called discovery. Called from
        example controller start method and from DISCOVER command recieved
        from ISY as an exmaple.
        """
        self.poly.addNode(GoveeNode(self.poly, self.address, 'templateaddr', 'Goove Name'))
        LOGGER.debug('discover')

    def delete(self):
        """
        Example
        This is call3ed by Polyglot upon deletion of the NodeServer. If the
        process is co-resident and controlled by Polyglot, it will be
        terminiated within 5 seconds of receiving this message.
        """
        LOGGER.info('Oh God I\'m being deleted. Nooooooooooooooooooooooooooooooooooooooooo.')

    def stop(self):
        """
        This is called by Polyglot when the node server is stopped.  You have
        the opportunity here to cleanly disconnect from your device or do
        other shutdown type tasks.
        """
        LOGGER.debug('NodeServer stopped.')


    """
    This is an example of implementing a heartbeat function.  It uses the
    long poll intervale to alternately send a ON and OFF command back to
    the ISY.  Programs on the ISY can then monitor this and take action
    when the heartbeat fails to update.
    """
    def heartbeat(self,init=False):
        LOGGER.debug('heartbeat: init={}'.format(init))
        if init is not False:
            self.hb = init
        LOGGER.debug('heartbeat: hb={}'.format(self.hb))
        if self.hb == 0:
            self.reportCmd("DON",2)
            self.hb = 1
        else:
            self.reportCmd("DOF",2)
            self.hb = 0

    def set_module_logs(self,level):
        logging.getLogger('urllib3').setLevel(level)

    def check_params(self):
        self.Notices.clear()

        # self.api_key = self.Parameters.api_key
        # if self.api_key is None:
        #     self.api_key = default_api_key
        #     LOGGER.error('check_params: api_key not defined in customParams, please add it.  Using {}'.format(default_password))


        # if self.api_key == default_api_key:
        #     self.Notices['api_key'] = 'Please set proper api_key in configuration page'
        # Typed Parameters allow for more complex parameter entries.
        # It may be better to do this during __init__() 

        # Lets try a simpler thing here
        self.TypedParameters.load( [
                {
                    'name': 'settings',
                    'title': 'Settings',
                    'desc': 'Govee Settings',
                    'isList': False,
                    'params': [
                        {
                            'name': 'api_key',
                            'title': 'API Key',
                            'isRequired': True,
                        },
                        {
                            'name': 'lan_control',
                            'title': 'Local LAN',
                            'defaultValue': False,
                            'isRequired': False,
                        },
                        {
                            'name': 'ble_control',
                            'title': 'Bluetooth (Not supported)',
                            'defaultValue': False,
                            'isRequired': False,
                        }
                    ]
                }
            ],
            True
        )

    def remove_notice_test(self,command):
        LOGGER.info('remove_notice_test: notices={}'.format(self.Notices))
        # # Remove the test notice
        self.Notices.delete('test')

    def remove_notices_all(self,command):
        LOGGER.info('remove_notices_all: notices={}'.format(self.Notices))
        # # Remove all existing notices
        self.Notices.clear()


    def device_changed(device: GoveeDevice):
        LOGGER.info('device_changed: device={}'.format(device))

    """
    Optional.
    Since the controller is a node in ISY, it will actual show up as a node.
    Thus it needs to know the drivers and what id it will use. The controller
    should report the node server status and have any commands that are
    needed to control operation of the node server.

    Typically, node servers will use the 'ST' driver to report the node server
    status and it a best pactice to do this unless you have a very good
    reason not to.

    The id must match the nodeDef id="controller" in the nodedefs.xml
    """
    id = 'controller'
    commands = {
        'QUERY': query,
        'DISCOVER': discover,
        # 'REMOVE_NOTICES_ALL': remove_notices_all,
        # 'REMOVE_NOTICE_TEST': remove_notice_test,
    }
    drivers = [
        {'driver': 'ST', 'value': 1, 'uom': 2},
    ]
