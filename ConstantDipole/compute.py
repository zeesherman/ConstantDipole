# This simple python interface activates the c++ ConstantDipole

# Import the C++ module.
from hoomd.ConstantDipole import _ConstantDipole

# MutualDipole2 extends a ForceCompute, so we need to bring in the base class
# force and some other parts from hoomd
import hoomd
import hoomd.md

from hoomd import _hoomd
from hoomd.md import _md
from hoomd.md import force
from hoomd.md.force import _force

import math

# The ConstantDipole class. Mirrors exactly MutualDipole2 but removes the dipole compute so that the plugin does not need cusp.
class ConstantDipole(hoomd.md.force._force):

    # Initialize the ConstantDipole class
    def __init__(self, group, conductivity, field, gradient=[0., 0., 0.], xi = 0.5, errortol = 1e-3,
                 fileprefix = "", period = 0, constantdipoleflag = 0):

        hoomd.util.print_status_line();

        # initialize base class
        hoomd.md.force._force.__init__(self);

        # Set the cutoff radius for the cell and neighbor lists. This form
        # ensures the calculations are within the specified error tolerance.
        self.rcut = math.sqrt(-math.log(errortol))/xi;

        # enable the force
        self.enabled = True;

        # initialize the reflected c++ class
        if not hoomd.context.exec_conf.isCUDAEnabled():
            hoomd.context.msg.error("Sorry, we have not written CPU code for mutual dipole calculations. \n");
            raise RuntimeError('Error creating ConstantDipole');
        else:
            # Create a new neighbor list
            cl_ConstantDipole = _hoomd.CellListGPU(hoomd.context.current.system_definition);
            hoomd.context.current.system.addCompute(cl_ConstantDipole, "ConstantDipole_cl");
            self.neighbor_list = _md.NeighborListGPUBinned(hoomd.context.current.system_definition, self.rcut, 0.4, cl_ConstantDipole);
            self.neighbor_list.setEvery(1, True);
            hoomd.context.current.system.addCompute(self.neighbor_list, "ConstantDipole_nlist");
            self.neighbor_list.countExclusions();

            # Add the new force to the system
            self.cpp_force = _ConstantDipole.ConstantDipole(hoomd.context.current.system_definition, group.cpp_group,
                                                           self.neighbor_list, conductivity, field, gradient, xi, errortol, fileprefix,
                                                           period, constantdipoleflag, hoomd.context.current.system.getCurrentTimeStep());
            hoomd.context.current.system.addCompute(self.cpp_force,self.force_name);

        # Set parameters for the dipole and force calculations
        self.cpp_force.SetParams();
    
        # Compute the dipoles and forces for the current time step so that the
        # electric/magnetic forces are used for the first update to particle positions.
        self.cpp_force.computeForces(hoomd.context.current.system.getCurrentTimeStep());

    # The integrator calls the update_coeffs function but there are no
    # coefficients to update, so this function does nothing
    def update_coeffs(self):
        pass

    # Update only the external field and gradient.  Faster than the update_parameters function.
    def update_field(self, field, gradient = [0, 0, 0]):
        self.cpp_force.UpdateField(field, gradient);

    # Update simulation parameters.  This is needed if any of the simulation
    # parameters change, including the volume fraction or shape of the simulation box.
    def update_parameters(self, conductivity, field, gradient = [0., 0., 0.], fileprefix = "", period = 0, constantdipoleflag = 0):
        self.cpp_force.UpdateParameters(field, conductivity, fileprefix, period, constantdipoleflag,
                                        hoomd.context.current.system.getCurrentTimeStep());
        self.cpp_force.SetParams();