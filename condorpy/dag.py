__author__ = 'sdc50'

from node import Node
import subprocess, re

#TODO: set initialdir that overrides jobs' initaildir?

class DAG(object):
    """

    """
    def __init__(self,name):
        """
        """
        self._name = name
        self._dag_file = ""
        self._node_set = set()

    def __str__(self):
        """
        """
        self.complete_set()
        jobs = ''
        relationships = ''
        for node in self._node_set:
            jobs += str(node)
            relationships += node.list_relations()

        result = '%s\n%s' % (jobs, relationships)

        return result

    def __repr__(self):
        """
        """
        pass

    @property
    def name(self):
        """
        """
        return self._name

    @property
    def cluster_id(self):
        """

        :return:
        """
        return self._cluster_id

    @property
    def node_set(self):
        """
        """
        return self._node_set

    @property
    def dag_file(self):
        """
        """
        return '%s.dag' % (self.name)

    def add_node(self, node):
        """
        """
        assert isinstance(node, Node)
        self._node_set.add(node)

    def submit(self, options=None):
        """
        ensures that all relatives of nodes in node_set are also added to the set before submitting
        """
        self.complete_set()
        self._write_dag_file()
        for node in self._node_set:
            node.job._write_job_file()

        args = ['condor_submit_dag']
        if options:
            args.append(options)
        args.append(self.dag_file)

        process = subprocess.Popen(args, stdout = subprocess.PIPE, stderr=subprocess.PIPE)
        out,err = process.communicate()

        if err:
            if re.match('WARNING',err):
                print(err)
            else:
                raise Exception(err)
        print(out)
        try:
            self._cluster_id = int(re.search('(?<=cluster |\*\* Proc )(\d*)', out).group(1))
        except:
            self._cluster_id = -1

        return self.cluster_id


    def complete_set(self):
        """
        """
        complete_node_set = set()
        for node in self.node_set:
            complete_node_set.add(node)
            complete_node_set = complete_node_set.union(node.get_all_family_nodes())

        self._node_set = complete_node_set

    def _write_dag_file(self):
        """
        """
        dag_file = open(self.dag_file, 'w')
        dag_file.write(self.__str__())
        dag_file.close()
