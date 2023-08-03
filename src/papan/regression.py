import operator
import random

from deap import algorithms
from deap import base
from deap import creator
from deap import tools
from deap import gp
from gplearn.genetic import SymbolicRegressor
import gplearn
import numpy as np
import sympy
from sympy import oo

# for reproduction
s = 0
random.seed(s)
np.random.seed(s)

x = sympy.Symbol("X0")
X = None
Y = None


def protected_log(x1):
    if x1 < 0 or abs(x1) < 1e-6:
        return 1
    return np.log(x1)


def protected_sqrt(x1):
    if x1 < 0:
        return 1
    return np.sqrt(x1)


# DEAP Setup.
pset = gp.PrimitiveSet("Main", 1)
pset.addPrimitive(operator.add, 2)
# pset.addPrimitive(operator.sub, 2)
pset.addPrimitive(operator.mul, 2)
# pset.addPrimitive(protectedDiv, 2)
# pset.addPrimitive(operator.neg, 1)
pset.addPrimitive(protected_log, 1, name="log")
pset.addPrimitive(protected_sqrt, 1, name="sqrt")
pset.addEphemeralConstant("rand101", lambda: random.randint(-10, 10))
pset.renameArguments(ARG0="X0")

creator.create("FitnessMin", base.Fitness, weights=(-1,))
creator.create("Individual", gp.PrimitiveTree, fitness=creator.FitnessMin)

toolbox = base.Toolbox()
toolbox.register("expr", gp.genGrow, pset=pset, min_=1, max_=2)
toolbox.register(
    "individual", tools.initIterate, creator.Individual, toolbox.expr
)
toolbox.register("population", tools.initRepeat, list, toolbox.individual)
toolbox.register("compile", gp.compile, pset=pset)


def evaluate(individual):
    """Evalute the fitness of an individual: MAE (mean absolute error)"""
    func = toolbox.compile(individual)
    Yp = np.array(list(map(func, X)))
    return (np.mean(np.abs(Y - Yp)),)


toolbox.register("evaluate", evaluate)
# toolbox.register("select", tools.selTournament, tournsize=3)
toolbox.register(
    "select",
    tools.selDoubleTournament,
    fitness_size=10,
    parsimony_size=1.9,
    fitness_first=True,
)
# toolbox.register("select", tools.selLexicase)
# ref_points = tools.uniform_reference_points(nobj=3, p=12)
# toolbox.register("select", tools.selNSGA3WithMemory(ref_points))
toolbox.register("mate", gp.cxOnePoint)
toolbox.register("expr_mut", gp.genFull, min_=0, max_=1)


def customMut(individual, expr, pset):
    """To handle multiple mutation operators"""
    r = random.random()
    if r < 0.5:
        individual = gp.mutUniform(individual, expr, pset)
    else:
        # apply shrink
        individual = gp.mutShrink(individual)
    return individual


# toolbox.register("mutate", gp.mutUniform, expr=toolbox.expr_mut, pset=pset)
toolbox.register("mutate", customMut, expr=toolbox.expr_mut, pset=pset)
# toolbox.register("migrate", tools.migRing, k=5, selection=tools.selBest,
#    replacement=tools.selRandom)

toolbox.decorate(
    "mate", gp.staticLimit(key=operator.attrgetter("height"), max_value=6)
)
toolbox.decorate(
    "mutate", gp.staticLimit(key=operator.attrgetter("height"), max_value=6)
)


def deap_symreg(x, y):
    global X, Y
    X = x
    Y = y

    pop = toolbox.population(n=300)
    hof = tools.HallOfFame(1)

    stats_fit = tools.Statistics(lambda ind: ind.fitness.values)
    stats_size = tools.Statistics(len)
    mstats = tools.MultiStatistics(fitness=stats_fit, size=stats_size)
    mstats.register("avg", np.mean)
    mstats.register("std", np.std)
    mstats.register("min", np.min)
    mstats.register("max", np.max)

    pop, log = algorithms.eaSimple(
        pop, toolbox, 0.5, 0.1, 40, stats=mstats, halloffame=hof, verbose=True
    )
    # print log
    result = hof[0]
    result = str(result).replace("add", "Add").replace("mul", "Mul")
    return sympy.simplify(result)


def gplearn_symreg(data):
    np.random.seed(0)  # for reproduction

    # Extract x and y from the data
    x = np.array([item[0] for item in data]).reshape(-1, 1)
    y = np.array([item[1] for item in data])

    # Create symbolic regressor
    # def _pow_exp(x1):
    #    with np.errstate(divide='ignore', invalid='ignore'):
    #        if (x1 > 10).any():
    #            return 0.
    #        try:
    #            result = np.power(2, x1)
    #            #print(result)
    #            return result
    #        except OverflowError:
    #            return 0.
    #        except ValueError:  # The math domain error
    #            return 0.
    #        except RuntimeWarning:
    #            return 0.

    # pow_exp = gplearn.functions.make_function(
    #    function=_pow_exp,
    #    name='pow_exp',
    #    arity=1
    # )
    # function_set=['add', 'mul', 'log', 'sqrt', pow_exp]
    function_set = ["add", "mul", "log", "sqrt"]
    sr = SymbolicRegressor(
        population_size=5000,
        generations=20,
        function_set=function_set,
        stopping_criteria=0.01,
        p_crossover=0.7,
        p_subtree_mutation=0.1,
        p_hoist_mutation=0.05,
        p_point_mutation=0.1,
        max_samples=0.9,
        verbose=0,
        parsimony_coefficient="auto",
        random_state=0,
        n_jobs=1,
        init_method="grow",
    )

    # Fit the data
    sr.fit(x, y)

    def to_sympy_expr(prog):
        """Convert a program to a sympy expression."""
        locals = {
            "sub": lambda x, y: x - y,
            "div": lambda x, y: x / y,
            "mul": lambda x, y: x * y,
            "add": lambda x, y: x + y,
            "neg": lambda x: -x,
            "pow": lambda x, y: x**y,
            "cos": lambda x: sympy.cos(x),
            "sqrt": lambda x: sympy.sqrt(x),
        }
        return sympy.simplify(sympy.sympify(str(prog), locals=locals))

    return to_sympy_expr(sr._program)
