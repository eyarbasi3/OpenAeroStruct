""" Example runscript to perform aerostructural analysis. """

from __future__ import division
import numpy
import sys
import time

from os import sys, path
sys.path.append(path.dirname(path.dirname(path.abspath(__file__))))

from openmdao.api import IndepVarComp, Problem, Group, ScipyOptimizer, Newton, ScipyGMRES, LinearGaussSeidel, NLGaussSeidel, SqliteRecorder
from geometry import GeometryMesh, Bspline, gen_crm_mesh, gen_rect_mesh
from transfer import TransferDisplacements, TransferLoads
from vlm import VLMStates, VLMFunctionals, VLMGeometry
from spatialbeam import SpatialBeamStates, SpatialBeamFunctionals, radii
from materials import MaterialsTube
from functionals import FunctionalBreguetRange, FunctionalEquilibrium

from openmdao.devtools.partition_tree_n2 import view_tree
from run_classes import OASProblem
from gs_newton import HybridGSNewton
from b_spline import get_bspline_mtx


# Set problem type
prob_dict = {'type' : 'aerostruct'}

# Instantiate problem and add default surface
OAS_prob = OASProblem(prob_dict)
OAS_prob.add_surface({'name' : '',
                      'wing_type' : 'CRM',
                      'num_y' : 13,
                      'num_x' : 2,
                      'span_cos_spacing' : 0,
                      'CL0' : 0.2,
                      'CD0' : 0.015})

# Get the created surface
surface = OAS_prob.surfaces[0]
prob_dict = OAS_prob.prob_dict
num_y = surface['num_y']
r = radii(surface['mesh'])
thickness = r / 10
thickness[:] = numpy.max((thickness))
num_twist = num_thickness = num_y

span = surface['span']
v = prob_dict['v']
alpha = prob_dict['alpha']
rho = prob_dict['rho']
M = prob_dict['M']
Re = prob_dict['Re']

# Create the top-level system
root = Group()

# Define the independent variables
indep_vars = [
    ('span', span),
    ('twist', numpy.zeros(num_twist)),
    ('thickness', thickness),
    ('v', v),
    ('alpha', alpha),
    ('rho', rho),
    ('r', r),
    ('M', M),
    ('Re', Re),
]

############################################################
# These are your components, put them in the correct groups.
# indep_vars_comp, tube_comp, and weiss_func_comp have been
# done for you as examples
############################################################

indep_vars_comp = IndepVarComp(indep_vars)
tube_comp = MaterialsTube(surface)

mesh_comp = GeometryMesh(surface)
geom_comp = VLMGeometry(surface)
spatialbeamstates_comp = SpatialBeamStates(surface)
def_mesh_comp = TransferDisplacements(surface)
vlmstates_comp = VLMStates(OAS_prob.surfaces, OAS_prob.prob_dict)
loads_comp = TransferLoads(surface)

vlmfuncs_comp = VLMFunctionals(surface)
spatialbeamfuncs_comp = SpatialBeamFunctionals(surface)
fuelburn_comp = FunctionalBreguetRange(OAS_prob.surfaces, OAS_prob.prob_dict)
eq_con_comp = FunctionalEquilibrium(OAS_prob.surfaces, OAS_prob.prob_dict)

############################################################
############################################################

root.add('indep_vars',
         indep_vars_comp,
         promotes=['*'])
root.add('tube',
         tube_comp,
         promotes=['*'])

# Add components to the MDA here
coupled = Group()
coupled.add('mesh',
    mesh_comp,
    promotes=["*"])
coupled.add('spatialbeamstates',
    spatialbeamstates_comp,
    promotes=["*"])
coupled.add('def_mesh',
    def_mesh_comp,
    promotes=["*"])
coupled.add('geom',
    geom_comp,
    promotes=["*"])
coupled.add('vlmstates',
    vlmstates_comp,
    promotes=["*"])
coupled.add('loads',
    loads_comp,
    promotes=["*"])

############################################################
# Comment/uncomment these solver blocks to try different
# nonlinear solver methods
############################################################

## Nonlinear Gauss Seidel on the coupled group
# coupled.nl_solver = NLGaussSeidel()
# coupled.nl_solver.options['iprint'] = 1
# coupled.nl_solver.options['atol'] = 1e-5
# coupled.nl_solver.options['rtol'] = 1e-12

## Newton Solver on the coupled group
# coupled.nl_solver = Newton()
# coupled.nl_solver.options['iprint'] = 1


## Hybrid NLGS-Newton on the coupled group
# coupled.nl_solver = HybridGSNewton()
# coupled.nl_solver.nlgs.options['iprint'] = 1
# coupled.nl_solver.nlgs.options['maxiter'] = 5
# coupled.nl_solver.newton.options['atol'] = 1e-7
# coupled.nl_solver.newton.options['rtol'] = 1e-7
# coupled.nl_solver.newton.options['iprint'] = 1


# Newton solver on the root group
root.nl_solver = Newton()
root.nl_solver.options['iprint'] = 1

###############################################
# Don't change the linear solver confuguration
###############################################
# linear solver configuration
coupled.ln_solver = ScipyGMRES()
coupled.ln_solver.options['iprint'] = 1
coupled.ln_solver.preconditioner = LinearGaussSeidel()
coupled.vlmstates.ln_solver = LinearGaussSeidel()
coupled.spatialbeamstates.ln_solver = LinearGaussSeidel()

# adds the MDA to root (do not remove!)
root.add('coupled',
         coupled,
         promotes=['*'])

# Add functional components here
root.add('vlmfuncs',
        vlmfuncs_comp,
        promotes=['*'])
root.add('spatialbeamfuncs',
        spatialbeamfuncs_comp,
        promotes=['*'])
root.add('fuelburn',
        fuelburn_comp,
        promotes=['*'])
root.add('eq_con',
        eq_con_comp,
        promotes=['*'])

prob = Problem()
prob.root = root
prob.print_all_convergence() # makes OpenMDAO print out solver convergence data

# change file name to save data from each experiment separately
prob.driver.add_recorder(SqliteRecorder('prob2b.db'))

prob.setup()
# uncomment this to see an n2 diagram of your problem
view_tree(prob, outfile="aerostruct_n2.html", show_browser=False)

st = time.time()
prob.run_once()
print "run time: {} secs".format(time.time() - st)
print "fuelburn:", prob['fuelburn']
