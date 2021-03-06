from threading import Thread


class Simulator:

    """
    Process a task by simulating one or more policies on one environment each.
    If multiple policies are provided, they will be simluated in parallel.
    """

    def __init__(self, task, policies, envs):
        self._task = task
        self._validate_input(policies, envs)
        self._policies = policies
        self._envs = envs

    def __iter__(self):
        while True:
            score = self.__call__()
            if score is None:
                return
            yield score

    def __call__(self, epochs=None):
        """
        Simulate on epoch of the task and return the average score. If the task
        is already done, return None.
        """
        if self._task.epoch >= self._task.epochs:
            return None
        self._task.epoch.increment()
        threads, scores = [], []
        amount = self._task.steps / self._task.epochs
        target = min(self._task.step + amount, self._task.steps)
        for env, policy in zip(self._envs, self._policies):
            args = target, env, policy, scores
            threads.append(Thread(target=self._worker, args=args))
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        return sum(scores) / len(scores) if scores else None

    def _worker(self, target, env, policy, scores):
        while self._task.step < target:
            score = self._episode(env, policy)
            scores.append(score)

    def _episode(self, env, policy):
        score = 0
        episode = self._task.episode.increment()
        policy.begin_episode(episode, self._task.training)
        # Other policies might run in parallel and update the episode counter
        # in the background. For the policy to see its own episode in the task,
        # we override the episode of this policy's task proxy.
        policy.task.episode = episode
        observ = env.reset()
        while observ is not None:
            action = policy.observe(observ)
            reward, observ = env.step(action)
            policy.receive(reward, observ is None)
            self._task.step.increment()
            score += reward
        policy.end_episode()
        # We undo the episode override after the task finishes..
        del policy.task.episode
        return score

    def _validate_input(self, policies, envs):
        if len(envs) != len(policies):
            ValueError('must provide one policy for each env')
        if not all(self._task.observs == x.observs for x in envs):
            ValueError('envs must match the task observation space')
        if not all(self._task.actions == x.actions for x in envs):
            ValueError('envs must match the task action space')
