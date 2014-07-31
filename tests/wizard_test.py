from contextlib import contextmanager
from contextlib import nested

import mock
import testify as T

import wizard
from service_wizard import autosuggest
from service_wizard import config
from service_wizard import service_configuration


class SrvReaderWriterTestCase(T.TestCase):
    """I bailed out of this test, but I'll leave this here for now as an
    example of how to interact with the Srv* classes."""
    @T.setup
    def init_service(self):
        paths = wizard.paths.SrvPathBuilder("fake_srvpathbuilder")
        self.srw = wizard.SrvReaderWriter(paths)

class ValidateOptionsTestCase(T.TestCase):
    def test_enable_yelpsoa_config_requires_yelpsoa_config_root(self):
        parser = mock.Mock()
        options = mock.Mock()
        options.enable_yelpsoa_config = True
        options.yelpsoa_config_root = None
        options.enable_puppet = False # Disable checks we don't care about
        options.enable_nagios = False # Disable checks we don't care about
        with T.assert_raises(SystemExit):
            wizard.validate_options(parser, options)

    def test_enable_puppet_requires_puppet_root(self):
        parser = mock.Mock()
        options = mock.Mock()
        options.enable_puppet = True
        options.puppet_root = None
        options.enable_yelpsoa_config = False # Disable checks we don't care about
        options.enable_nagios = False # Disable checks we don't care about
        with T.assert_raises(SystemExit):
            wizard.validate_options(parser, options)

    def test_enable_nagios_requires_nagios_root(self):
        parser = mock.Mock()
        options = mock.Mock()
        options.enable_nagios = True
        options.nagios_root = None
        options.enable_yelpsoa_config = False # Disable checks we don't care about
        options.enable_puppet = False # Disable checks we don't care about
        with T.assert_raises(SystemExit):
            wizard.validate_options(parser, options)

class SuggestPortTestCase(T.TestCase):
    def test_suggest_port(self):
        # mock.patch was very confused by the config module, so I'm doing it
        # this way. One more reason to disapprove of this global config module
        # scheme.
        config.YELPSOA_CONFIG_ROOT = "fake_yelpsoa_config_root"

        walk_return = [(
            "fake_root",
            "fake_dir",
            [
                "fake_file", # ignored
                "repl_delay_reporter.yaml", # contains 'port' but ignored
                "port",
                "status_port",
                "weird_port", # has bogus out-of-range value
            ]
        )]
        mock_walk = mock.Mock(return_value=walk_return)

        # See http://www.voidspace.org.uk/python/mock/examples.html#multiple-calls-with-different-effects
        get_port_from_file_returns = [
            13001,
            13002,
            55555, # bogus out-of-range value
        ]
        def get_port_from_file_side_effect(*args):
            return get_port_from_file_returns.pop(0)
        mock_get_port_from_file = mock.Mock(side_effect=get_port_from_file_side_effect)
        with nested(
            mock.patch("os.walk", mock_walk),
            mock.patch("service_wizard.autosuggest._get_port_from_file", mock_get_port_from_file),
        ):
            actual = autosuggest.suggest_port()
        # Sanity check: our mock was called once for each legit port file in
        # walk_return
        T.assert_equal(mock_get_port_from_file.call_count, 3)

        # What we came here for: the actual output of the function under test
        T.assert_equal(actual, 13002 + 1) # highest port + 1

# Shamelessly copied from SuggestPortTestCase
class SuggestSmartstackProxyPortTestCase(T.TestCase):
    def test_suggest_smartstack_proxy_port(self):
        # mock.patch was very confused by the config module, so I'm doing it
        # this way. One more reason to disapprove of this global config module
        # scheme.
        config.YELPSOA_CONFIG_ROOT = "fake_yelpsoa_config_root"

        walk_return = [
            ("fake_root1", "fake_dir1", [ "service.yaml" ]),
            ("fake_root2", "fake_dir2", [ "service.yaml" ]),
            ("fake_root3", "fake_dir3", [ "service.yaml" ]),
        ]
        mock_walk = mock.Mock(return_value=walk_return)

        # See http://www.voidspace.org.uk/python/mock/examples.html#multiple-calls-with-different-effects
        get_smartstack_proxy_port_from_file_returns = [
            20001,
            20002,
            55555, # bogus out-of-range value
        ]
        def get_smarstack_proxy_port_from_file_side_effect(*args):
            return get_smartstack_proxy_port_from_file_returns.pop(0)
        mock_get_smartstack_proxy_port_from_file = mock.Mock(side_effect=get_smarstack_proxy_port_from_file_side_effect)
        with nested(
            mock.patch("os.walk", mock_walk),
            mock.patch("service_wizard.autosuggest._get_smartstack_proxy_port_from_file",
                       mock_get_smartstack_proxy_port_from_file),
        ):
            actual = autosuggest.suggest_smartstack_proxy_port()
        # Sanity check: our mock was called once for each legit port file in
        # walk_return
        T.assert_equal(mock_get_smartstack_proxy_port_from_file.call_count, 3)

        # What we came here for: the actual output of the function under test
        T.assert_equal(actual, 20002 + 1) # highest port + 1

class SuggestRunsOnTestCase(T.TestCase):
    @T.setup_teardown
    def mock_service_configuration_lookups(self):
        with nested(
            mock.patch("service_wizard.service_configuration.load_service_yamls"),
            mock.patch("service_wizard.service_configuration.collate_service_yamls"),
            mock.patch("service_wizard.autosuggest.suggest_all_hosts", return_value=""),
            mock.patch("service_wizard.autosuggest.suggest_hosts_for_habitat", return_value=""),
        ) as (self.mock_load_service_yamls, _, _, _):
                yield

    def test_returns_original_if_no_munging_occurred(self):
        expected = "things,not,needing,munging"
        actual = autosuggest.suggest_runs_on(expected)
        T.assert_equal(expected, actual)

    def test_does_not_load_yamls_if_no_munging_occurred(self):
        runs_on = "things,not,needing,munging"
        autosuggest.suggest_runs_on(runs_on)
        T.assert_equal(0, self.mock_load_service_yamls.call_count)

    def test_loads_yamls_if_auto(self):
        runs_on = "AUTO"
        autosuggest.suggest_runs_on(runs_on)
        T.assert_equal(1, self.mock_load_service_yamls.call_count)

    def test_loads_yamls_if_HABITAT(self):
        runs_on = "FAKE_HABITAT1"
        autosuggest.suggest_runs_on(runs_on)
        T.assert_equal(1, self.mock_load_service_yamls.call_count)

class DiscoverHabitatsTestCase(T.TestCase):
    def test_stage(self):
        collated_service_yamls = {
            "stagex": {
                "stagexhost": 1,
            },
            "xstage": {
                "should_not_be_included": 1,
            },
        }
        habitats = autosuggest.discover_habitats(collated_service_yamls)
        T.assert_in("stagex", habitats)
        T.assert_not_in("xstage", habitats)

    def test_prod(self):
        # Prod values are hardcoded, so even with no discovered habitats they
        # should appear.
        collated_service_yamls = {}
        habitats = autosuggest.discover_habitats(collated_service_yamls)
        T.assert_in("iad1", habitats)

    def test_dev(self):
        collated_service_yamls = {
            "devx": {
                "devxhost": 1,
            },
            "xdev": {
                "should_not_be_included": 1,
            },
        }
        habitats = autosuggest.discover_habitats(collated_service_yamls)
        T.assert_in("devx", habitats)
        T.assert_not_in("xdev", habitats)

class SuggestHostsForHabitat(T.TestCase):
    def test_habitat_not_in_collated_service_yamls(self):
        collated_service_yamls = {}
        actual = autosuggest.suggest_hosts_for_habitat(collated_service_yamls, "nonexistent")
        T.assert_equal("", actual)

    def test_not_prod(self):
        """All non-prod habitats have the same workflow, so just test one."""
        expected = "stagexservices1"
        collated_service_yamls = {
            "stagex": {
                expected: 5,
                "stagexservices2": 10,
                "stagex-ineligibile-non-services-box3": 1,
            },
        }
        actual = autosuggest.suggest_hosts_for_habitat(collated_service_yamls, "stagex")
        T.assert_equal(expected, actual)

    def test_prod(self):
        expected = "srv1,srv1-r1-iad1"
        collated_service_yamls = {
            "sfo1": {
                "srv1": 99,
                "srv1-r1-iad1": 99,
                "mon1": 1,
                "search1": 1,
            },
        }
        actual = autosuggest.suggest_hosts_for_habitat(collated_service_yamls, "sfo1")
        T.assert_equal(expected, actual)

class SuggestAllHostsTestCase(T.TestCase):
    @T.setup_teardown
    def mock_suggest_hosts_for_habitat(self):
        with mock.patch(
            "service_wizard.autosuggest.suggest_hosts_for_habitat",
            return_value="fake_list_of_hosts",
        ) as self.mock_suggest_hosts_for_habitat:
            yield

    def test_calls_suggest_hosts_for_habitat(self):
        autosuggest.suggest_all_hosts({"unused": "dict"})
        # Make sure we try to suggest at least one habitat.
        T.assert_gt(self.mock_suggest_hosts_for_habitat.call_count, 0)

class LoadServiceYamls(T.TestCase):
    """load_service_yamls() is mostly just a wrapper around python fundamentals
    (import, os.walk) and service_configuration_lib.read_service_information
    (tested elsewhere). Hence, there aren't a lot of tests here.
    """
    @T.setup_teardown
    def setup_config(self):
        config.YELPSOA_CONFIG_ROOT = "non_empty_unused_yelpsoa_config_root"
        config.PUPPET_ROOT = "non_empty_unused_puppet_root"
        # The method under test short circuits and returns [] if something goes wrong. If
        # we get past that point, hit mocks rather than acutally reading things
        # off disk.
        self.fake_load_service_yamls_from_disk = ["fake", "service", "information"]
        with mock.patch(
            "service_wizard.service_configuration._load_service_yamls_from_disk",
            return_value=self.fake_load_service_yamls_from_disk
        ):
            yield

    def test_returns_empty_list_when_yelpsoa_config_root_not_set(self):
        config.YELPSOA_CONFIG_ROOT = None
        T.assert_equal([], service_configuration.load_service_yamls())

    def test_returns_something_when_puppet_root_not_set(self):
        config.PUPPET_ROOT = None
        T.assert_equal(self.fake_load_service_yamls_from_disk, service_configuration.load_service_yamls())

class CollateServiceYamlsTestCase(T.TestCase):
    @T.setup_teardown
    def mock_get_habitat_from_fqdn(self):
        """This test case only cares about the logic in
        parse_hostnames_string(), so patch get_fqdn() to just return what we
        give it.
        """
        def fake_get_habitat_from_fqdn(hostname):
            if hostname is None:
                return hostname
            habitat = None
            try:
                hostname, habitat = hostname.split(".")
            except ValueError:
                pass
            return habitat
        with mock.patch("service_wizard.service_configuration.get_habitat_from_fqdn", new=fake_get_habitat_from_fqdn):
            yield

    def test_collate_service_yamls_returns_empty_dict_given_empty_list(self):
        expected = {}
        all_service_yamls = []
        actual = service_configuration.collate_service_yamls(all_service_yamls)
        T.assert_equal(expected, actual)

    def test_collate_service_yamls_returns_empty_dict_given_one_invalid_host(self):
        expected = {}
        all_service_yamls = [
            {
                "runs_on": ["host_with_no_habitat"],
            }
        ]
        actual = service_configuration.collate_service_yamls(all_service_yamls)
        T.assert_equal(expected, actual)

    def test_collate_service_yamls_returns_empty_dict_given_list_of_none(self):
        """This happes with yaml like this:
        runs_on:
         -
        deploys_on:
         - somebatch.sfo1
         """
        expected = {}
        all_service_yamls = [
            {
                "runs_on": [None],
            }
        ]
        actual = service_configuration.collate_service_yamls(all_service_yamls)
        T.assert_equal(expected, actual)

    def test_collate_service_yamls_returns_empty_dict_given_yaml_without_runs_on(self):
        """This happes with yaml like this:
         needs_puppet_help: true
         """
        expected = {}
        all_service_yamls = [
            {
                "needs_puppet_help": True,
            }
        ]
        actual = service_configuration.collate_service_yamls(all_service_yamls)
        T.assert_equal(expected, actual)

    def test_collate_service_yamls_one_service_one_habitat(self):
        hosts = ["host1.habitat1", "anotherhost1.habitat1"]
        expected = { "habitat1": {
            hosts[0]: 1,
            hosts[1]: 1,
        }}
        all_service_yamls = [
            {
                "runs_on": hosts,
                "deployed_to": [""],
                "unused_key": ["car"],
            },
        ]
        actual = service_configuration.collate_service_yamls(all_service_yamls)
        T.assert_equal(expected, actual)

    def test_collate_service_yamls_one_service_two_habitats(self):
        hosts = ["host1.habitat1", "host2.habitat2"]
        expected = {
            "habitat1": { hosts[0]: 1 },
            "habitat2": { hosts[1]: 1 },
        }
        all_service_yamls = [
            {
                "runs_on": hosts,
                "deployed_to": [""],
                "unused_key": ["car"],
            },
        ]
        actual = service_configuration.collate_service_yamls(all_service_yamls)
        T.assert_equal(expected, actual)

    def test_collate_service_yamls_two_services_one_habitat(self):
        hosts = ["host1.habitat1", "anotherhost1.habitat1"]
        expected = { "habitat1": {
                hosts[0]: 1,
                hosts[1]: 1,
        }}
        all_service_yamls = [
            {
                "runs_on": [hosts[0]],
                "deployed_to": [""],
                "unused_key": ["car"],
            },
            {
                "runs_on": [hosts[1]],
                "deployed_to": [""],
                "unused_key": ["car"],
            },
        ]
        actual = service_configuration.collate_service_yamls(all_service_yamls)
        T.assert_equal(expected, actual)

class ParseHostnamesStringTestCase(T.TestCase):
    @T.setup_teardown
    def mock_get_fqdn(self):
        """This test case only cares about the logic in
        parse_hostnames_string(), so patch get_fqdn() to just return what we
        give it.
        """
        def fake_get_fqdn(hostname):
            return hostname
        with mock.patch("wizard.get_fqdn", new=fake_get_fqdn):
            yield

    def test_empty(self):
        runs_on = ""
        expected = []
        actual = wizard.parse_hostnames_string(runs_on)
        T.assert_equal(expected, actual)

    def test_one_runs_on(self):
        runs_on = "runs_on1"
        expected = [runs_on]
        actual = wizard.parse_hostnames_string(runs_on)
        T.assert_equal(expected, actual)

    def test_two_runs_on(self):
        runs_on = "runs_on1,runs_on2"
        expected = ["runs_on1", "runs_on2"]
        actual = wizard.parse_hostnames_string(runs_on)
        T.assert_equal(expected, actual)

    def test_two_runs_on_with_space(self):
        runs_on = "runs_on1, runs_on2"
        expected = ["runs_on1", "runs_on2"]
        actual = wizard.parse_hostnames_string(runs_on)
        T.assert_equal(expected, actual)

class GetServiceYamlContentsTestCase(T.TestCase):
    def test_empty(self):
        runs_on = []
        deploys_on = []
        smartstack = None
        actual = wizard.get_service_yaml_contents(runs_on, deploys_on, smartstack)

        # Verify entire lines to make sure that e.g. '---' appears as its own
        # line and not as part of 'crazy---service----name'.
        T.assert_in("---\n", actual)
        # I think a blank line would be better but I can't figure out how to
        # get pyyaml to emit that.
        T.assert_in("runs_on: []", actual)
        T.assert_in("deployed_to: []", actual)

    def test_one_runs_on(self):
        runs_on = ["runs_on1"]
        deploys_on = []
        smartstack = None
        actual = wizard.get_service_yaml_contents(runs_on, deploys_on, smartstack)

        expected = "runs_on:\n- %s" % "runs_on1"
        T.assert_in(expected, actual)

    def test_two_runs_on(self):
        runs_on = ["runs_on1", "runs_on2"]
        deploys_on = []
        smartstack = None
        actual = wizard.get_service_yaml_contents(runs_on, deploys_on, smartstack)

        expected = "runs_on:\n- %s\n- %s" % ("runs_on1", "runs_on2")
        T.assert_in(expected, actual)

    def test_smartstack(self):
        runs_on = []
        deploys_on = []
        smartstack = {"proxy_port": 1234}
        actual = wizard.get_service_yaml_contents(runs_on, deploys_on, smartstack)

        expected = "smartstack:\n  proxy_port: 1234\n"
        T.assert_in(expected, actual)


class GetHabitatFromFqdnTestCase(T.TestCase):
    def test_none(self):
        fqdn = None
        expected = None
        actual = service_configuration.get_habitat_from_fqdn(fqdn)
        T.assert_equal(expected, actual)

    def test_unknown(self):
        fqdn = "unknownhost.unknownsubdomain.yelpcorp.com"
        expected = None
        actual = service_configuration.get_habitat_from_fqdn(fqdn)
        T.assert_equal(expected, actual)

    def test_hostname_only(self):
        """Exercises the case where the fqdn doesn't match our expectations to
        make sure it doesn't blow up *and* that it returns a miss.
        """
        fqdn = "short-host-only"
        expected = None
        actual = service_configuration.get_habitat_from_fqdn(fqdn)
        T.assert_equal(expected, actual)

    def test_stagea(self):
        fqdn = "stageaservices1.sldev.yelpcorp.com"
        expected = "stagea"
        actual = service_configuration.get_habitat_from_fqdn(fqdn)
        T.assert_equal(expected, actual)

    ###### decide what to do with spam habitats
    def test_stagespam_is_not_stage(self):
        """I'm not sure what to do with stagespam yet (I think it gets its own
        Nagios file) but the point of this test is to make sure STAGE_RE
        doesn't match stagespam so we'll only assert about that fact.
        """
        fqdn = "stagespam1sv.sldev.yelpcorp.com"
        actual = service_configuration.get_habitat_from_fqdn(fqdn)
        T.assert_not_equal("stage", actual)

    def test_devb(self):
        fqdn = "srv2-devb.dev.yelpcorp.com"
        expected = "devb"
        actual = service_configuration.get_habitat_from_fqdn(fqdn)
        T.assert_equal(expected, actual)

    def test_old_sfo1(self):
        """Some sfo1 hosts do not conform to the standard habitat naming
        convention, in particular not having any habitat. These are limited
        to sfo1."""
        fqdn = "search26.prod.yelpcorp.com"
        expected = "sfo1"
        actual = service_configuration.get_habitat_from_fqdn(fqdn)
        T.assert_equal(expected, actual)

    def test_sfo1(self):
        fqdn = "srv3-r1-sfo1.prod.yelpcorp.com"
        expected = "sfo1"
        actual = service_configuration.get_habitat_from_fqdn(fqdn)
        T.assert_equal(expected, actual)

    def test_iad1(self):
        fqdn = "srv4-r4-iad1.prod.yelpcorp.com"
        expected = "iad1"
        actual = service_configuration.get_habitat_from_fqdn(fqdn)
        T.assert_equal(expected, actual)

    def test_365(self):
        fqdn = "srv1.365.yelpcorp.com"
        expected = "sfo1"
        actual = service_configuration.get_habitat_from_fqdn(fqdn)
        T.assert_equal(expected, actual)

    def test_sldev(self):
        fqdn = "devsearch2sv.sldev.yelpcorp.com"
        expected = "sldev"
        actual = service_configuration.get_habitat_from_fqdn(fqdn)
        T.assert_equal(expected, actual)

    def test_slwdc(self):
        fqdn = "app3sw.slwdc.yelpcorp.com"
        expected = "slwdc"
        actual = service_configuration.get_habitat_from_fqdn(fqdn)
        T.assert_equal(expected, actual)

    def test_sj(self):
        fqdn = "devsearch2sj.sjc.yelpcorp.com"
        expected = "sjc"
        actual = service_configuration.get_habitat_from_fqdn(fqdn)
        T.assert_equal(expected, actual)

    def test_relengsrv1_devc_testopia(self):
        fqdn = "relengsrv1-sjc.dev.yelpcorp.com"
        expected = "testopia"
        actual = service_configuration.get_habitat_from_fqdn(fqdn)
        T.assert_equal(expected, actual)


class CollateHostsByHabitat(T.TestCase):
    @contextmanager
    def patch_get_habitat_from_fqdn(self, return_value=None):
        def fake_get_habitat_from_fqdn(fqdn):
            return return_value or "%s-habitat" % fqdn
        with mock.patch("service_wizard.service_configuration.get_habitat_from_fqdn", fake_get_habitat_from_fqdn):
            yield

    def test_no_fqdns(self):
        expected = {}
        fqdns = []
        actual = service_configuration.collate_hosts_by_habitat(fqdns)
        T.assert_equal(expected, actual)

    def test_bad_fqdn_is_dropped(self):
        expected = {}
        fqdns = ["bad_fqdn"]
        actual = service_configuration.collate_hosts_by_habitat(fqdns)
        T.assert_equal(expected, actual)

    def test_one_good_fqdn(self):
        fqdn = "fakehost1.fakehabitat.yelpcorp.com"
        expected = {"%s-habitat" % fqdn: ["fakehost1"]}
        fqdns = [fqdn]
        with self.patch_get_habitat_from_fqdn():
            actual = service_configuration.collate_hosts_by_habitat(fqdns)
        T.assert_equal(expected, actual)

    def test_two_good_fqdns_different_habitat(self):
        fqdn1 = "fakehost1.fakehabitat.yelpcorp.com"
        fqdn2 = "fakehost2.fakehabitat.yelpcorp.com"
        expected = {
            "%s-habitat" % fqdn1: ["fakehost1"],
            "%s-habitat" % fqdn2: ["fakehost2"],
        }
        fqdns = [fqdn1, fqdn2]
        with self.patch_get_habitat_from_fqdn():
            actual = service_configuration.collate_hosts_by_habitat(fqdns)
        T.assert_equal(expected, actual)

    def test_two_good_fqdns_same_habitat(self):
        fqdn1 = "fakehost1.samehabitat.yelpcorp.com"
        fqdn2 = "fakehost2.samehabitat.yelpcorp.com"
        habitat = "samehabitat"
        expected = {habitat: ["fakehost1", "fakehost2"]}
        fqdns = [fqdn1, fqdn2]
        with self.patch_get_habitat_from_fqdn(habitat):
            actual = service_configuration.collate_hosts_by_habitat(fqdns)
        T.assert_equal(expected, actual)


#class GetHabitatOverrides(T.TestCase):
#    @T.setup_teardown
#    def patch_template(self):
#        with mock.patch("wizard.Template") as self.mock_template:
#            with mock.patch.object(self.mock_template, "substitute") as self.mock_substitute:
#                yield
#
#    def test_empty(self):
#        srvname = "fake_srvname"
#        host_by_habitat = {}
#        expected = {}
#        actual = wizard.get_habitat_overrides(host_by_habitat, srvname)
#        T.assert_equal(expected, actual)
#
#    def test_good_host_by_habitat(self):
#        srvname = "fake_srvname"
#        host_by_habitat = {"fake_habitat": ["fakehost1", "fakehost2"]}
#        wizard.get_habitat_overrides(host_by_habitat, srvname)
#
#        import ipdb; ipdb.set_trace()
#        assert self.mock_substitute.called
#        template_dict = self.mock_substitute.call_args[1]
#        print template_dict


if __name__ == "__main__":
    T.run()