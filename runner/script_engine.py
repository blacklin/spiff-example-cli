import subprocess, os, json

import datetime

from RestrictedPython import safe_globals

from SpiffWorkflow.bpmn.PythonScriptEngine import PythonScriptEngine
from SpiffWorkflow.bpmn.PythonScriptEngineEnvironment import BasePythonScriptEngineEnvironment, TaskDataEnvironment
from SpiffWorkflow.util.deep_merge import DeepMerge

from runner.product_info import (
    lookup_product_info,
    lookup_shipping_cost,
    loads,
    dumps,
    product_info_to_dict,
    product_info_from_dict
)

env_globals = {
    'lookup_product_info': lookup_product_info,
    'lookup_shipping_cost': lookup_shipping_cost,
    'datetime': datetime,
}
custom_env = TaskDataEnvironment(env_globals)
custom_script_engine = PythonScriptEngine(environment=custom_env)


restricted_env = TaskDataEnvironment(safe_globals)
restricted_script_engine = PythonScriptEngine(environment=restricted_env)


class SubprocessScriptingEnvironment(BasePythonScriptEngineEnvironment):

    def __init__(self, executable, **kwargs):
        super().__init__(**kwargs)
        self.executable = executable

    def evaluate(self, expression, context, external_methods=None):
        output = self.run(['eval', '-e', expression], context, external_methods)
        return self.parse_output(output)

    def execute(self, script, context, external_methods=None):
        output = self.run(['exec', '-s', script], context, external_methods)
        DeepMerge.merge(context, self.parse_output(output))
        return True

    def run(self, args, context, external_methods):
        cmd = [self.executable] + args + ['-l', dumps(context)]
        if external_methods is not None:
            cmd.extend(['-g', dumps(external_methods)])
        return subprocess.run(cmd, capture_output=True)

    def parse_output(self, output):
        if output.stderr:
            raise Exception(output.stderr)
        return loads(output.stdout)

executable = os.path.join(os.path.dirname(__file__), 'subprocess.py')
subprocess_script_engine = PythonScriptEngine(environment=SubprocessScriptingEnvironment(executable))


service_task_env = TaskDataEnvironment({
    'product_info_from_dict': product_info_from_dict,
    'datetime': datetime,
})

class ServiceTaskEngine(PythonScriptEngine):

    def __init__(self):
        super().__init__(environment=service_task_env)

    def call_service(self, operation_name, operation_params, task_data):
        if operation_name == 'lookup_product_info':
            product_info = lookup_product_info(operation_params['product_name']['value'])
            result = product_info_to_dict(product_info)
        elif operation_name == 'lookup_shipping_cost':
            result = lookup_shipping_cost(operation_params['shipping_method']['value'])
        else:
            raise Exception("Unknown Service!")
        return json.dumps(result)

service_task_engine = ServiceTaskEngine()