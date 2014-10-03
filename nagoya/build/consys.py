import logging

import nagoya.toji

logger = logging.getLogger("nagoya.build")

class BuildContainerSystem(nagoya.toji.TempToji):
    """
    Succinctly construct a system of containers and produce images from them in
    multiple ways.
    """

    def __init__(self, root_image, containers=None, client=None, cleanup=None):
        super(BuildContainerSystem, self).__init__(containers=containers, client=client, cleanup=cleanup)
        self.root = self._root(root_image)
        self.to_commit = []
        self.to_persist = []

    def _root(self, image_name):
        root = self.container(image=image_name, detach=False)
        self.containers.append(root)
        return root

    def commit(self, container):
        self.to_commit.append(container)

    def persist(self, container):
        self.to_persist.append(container)

    def _run(self):
        # TODO start system, wait until root is done, stop system
        pass

    def _build(self):
        pass # TODO

    def __exit__(self, exc, value, tb):
        try:
            try:
                if exc is None:
                    self._run()
            finally:
                pass
                # TODO close tempdirs after run?

            if exc is None:
                self._build()
        finally:
            super(BuildContainerSystem, self).__exit__(exc, value, tb)
