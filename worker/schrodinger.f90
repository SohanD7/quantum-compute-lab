module schrodinger_mod

  use, intrinsic :: iso_c_binding, only: c_double, c_int
  implicit none

contains

  ! ---------------------------------------------------------------
  ! compute_wave_matrix
  !   Computes a 2D Gaussian-modulated wave function approximation
  !   for a single time-step slice of the Schrödinger equation.
  !
  ! Arguments (exposed to Python via f2py):
  !   size_n    - grid dimension (NxN matrix)
  !   matrix    - output NxN wave amplitude matrix
  !   num_steps - total time steps (used as time-step index k)
  !   h_bar     - reduced Planck constant
  !   mass      - particle mass
  ! ---------------------------------------------------------------
  subroutine compute_wave_matrix(size_n, matrix, num_steps, h_bar, mass)

    implicit none

    ! --- Scalar inputs ---
    integer(c_int), intent(in)     :: size_n
    integer(c_int), intent(in)     :: num_steps
    real(c_double), intent(in)     :: h_bar
    real(c_double), intent(in)     :: mass

    ! --- 2D array output ---
    real(c_double), intent(inout)  :: matrix(size_n, size_n)

    ! --- Local variables (MUST be declared here, before executables) ---
    integer        :: i, j, k
    real(c_double) :: dx, dy, x, y, wave_value

    ! Grid spacing
    dx = 1.0_c_double / real(size_n - 1, c_double)
    dy = 1.0_c_double / real(size_n - 1, c_double)

    ! Use num_steps as the time-step index to modulate the wave phase
    k = num_steps

    do i = 1, size_n
      do j = 1, size_n

        ! Spatial coordinates in [0, 1]
        x = real(i - 1, c_double) * dx
        y = real(j - 1, c_double) * dy

        ! Gaussian envelope centered at (0.5, 0.5)
        wave_value = exp( &
          -100.0_c_double * ( &
            (x - 0.5_c_double)**2 + &
            (y - 0.5_c_double)**2  &
          ) &
        )

        ! Modulate amplitude with sinusoidal time phase
        matrix(i, j) = wave_value * sin(real(k, c_double) * 3.14159265358979_c_double)

      end do
    end do

  end subroutine compute_wave_matrix

end module schrodinger_mod
