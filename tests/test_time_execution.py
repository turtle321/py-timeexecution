import unittest

from influxdb.influxdb08.client import InfluxDBClientError
from time_execution import configure, time_execution
from time_execution.backends.influxdb import InfluxBackend


@time_execution
def go(*args, **kwargs):
    return True


@time_execution
def fqn_test():
    pass


@time_execution
class Dummy(object):
    @time_execution
    def go(self, *args, **kwargs):
        pass


class TestTimeExecution(unittest.TestCase):
    def setUp(self):
        super(TestTimeExecution, self).setUp()

        self.database = 'unittest'
        self.backend = InfluxBackend(
            host='influx',
            database=self.database,
            use_udp=False
        )

        try:
            self.backend.client.create_database(self.database)
        except InfluxDBClientError:
            # Something blew up so ignore it
            pass

        configure(backends=[self.backend])

    def tearDown(self):
        self.backend.client.delete_database(self.database)

    def _query_influx(self, name):
        query = 'select * from {}'.format(name)
        metrics = self.backend.client.query(query)[0]
        for metric in metrics['points']:
            yield dict(zip(metrics['columns'], metric))

    def test_fqn(self):
        self.assertEqual(fqn_test.fqn, 'tests.test_time_execution.fqn_test')
        self.assertEqual(Dummy.fqn, 'tests.test_time_execution.Dummy')
        self.assertEqual(Dummy().go.fqn, 'tests.test_time_execution.Dummy.go')

    def test_time_execution(self):

        count = 4

        for i in range(count):
            go()

        metrics = list(self._query_influx(go.fqn))
        self.assertEqual(len(metrics), count)

        for metric in metrics:
            self.assertTrue('value' in metric)

    def test_duration_field(self):

        configure(backends=[self.backend], duration_field='my_duration')

        go()

        for metric in self._query_influx(go.fqn):
            self.assertTrue('my_duration' in metric)

    def test_with_arguments(self):
        go('hello', world='world')
        Dummy().go('hello', world='world')

        metrics = list(self._query_influx(go.fqn))
        self.assertEqual(len(metrics), 1)

        metrics = list(self._query_influx(Dummy().go.fqn))
        self.assertEqual(len(metrics), 1)

    def test_hook(self):

        def test_args(**kwargs):
            self.assertIn('response', kwargs)
            self.assertIn('exception', kwargs)
            self.assertIn('metric', kwargs)
            return dict()

        def test_metadata(*args, **kwargs):
            return dict(test_key='test value')

        configure(backends=[self.backend], hooks=[test_args, test_metadata])

        go()

        for metric in self._query_influx(go.fqn):
            self.assertEqual(metric['test_key'], 'test value')

    def test_time_execution_with_exception(self):

        def exception_hook(exception, **kwargs):
            self.assertTrue(exception)
            return dict(exception_message=str(exception))

        configure(backends=[self.backend], hooks=[exception_hook])

        class TimeExecutionException(Exception):
            message = 'default'

        @time_execution
        def go():
            raise TimeExecutionException('test exception')

        with self.assertRaises(TimeExecutionException):
            go()

        for metric in self._query_influx(go.fqn):
            self.assertEqual(metric['exception_message'], 'test exception')
