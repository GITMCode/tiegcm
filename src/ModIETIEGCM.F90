module ModIETIEGCM
#ifdef HAVEMILE
  use ModIE
  use params_module, only: nmlon, nmlat
  implicit none

  type(ieModel), save :: ie

contains

  subroutine init_ie()
    use input_module, only: potential_model, aurora_model
    implicit none

    ie = iemodel()

    ! Set the names of the models (from .inp namelist)
    call ie%efield_model(potential_model)
    if (aurora_model /= 'emery') then
      call ie%aurora_model(aurora_model)
    else
      call ie%aurora_model('zero')
    endif

    ! Point to Electrodynamics data
    call ie%model_dir("../ext/Electrodynamics/data/ext/")
    
    ! Initialize the IE library
    call ie%init()

  end subroutine init_ie

  subroutine update_ie_potential(byimf_in, bzimf_in, swvel_in, swden_in)
    use params_module, only: nmlon, nmlonp1, nmlat
    use cons_module, only: ylonm, ylatm, pi
    use input_module, only: potential_model, ctpoten, power
    use magfield_module, only: sunlons
    use pdynamo_module, only: phihm, nmlat0
    use init_module, only: iyear, iday, uthr
    use wei05sc, only: cvt2md
    use aurora_module, only: ie_eflux_mag, ie_avee_mag

    implicit none

    integer :: iMlt, iLat
    real, allocatable :: potential(:, :)
    real, intent(in), optional :: byimf_in, bzimf_in, swvel_in, swden_in
    integer :: imo, ida, ihour, imin, isec


    if (ie%iEfield_ == iWeimer05_) then
      if (present(byimf_in)) ie%needImfBy = byimf_in
      if (present(bzimf_in)) ie%needImfBz = bzimf_in
      if (present(swvel_in)) ie%needSwV = swvel_in
      if (present(swden_in)) ie%needSwN = swden_in
    endif

      ! Update time in Electrodynamics (this computes tilt for Weimer05!)
      call cvt2md(6, iyear, iday, imo, ida)
      ihour = int(uthr)
      imin = int((uthr - real(ihour))*60.0)
      isec = 0
      call ie%time_ymdhms(iyear, imo, ida, ihour, imin, isec)

    ! Update grid dynamically because MLT changes with time 'sunlons'
    if (ie%neednMLTs /= nmlon .or. ie%neednLats /= nmlat) then
      ie%neednMLTs = nmlon
      ie%neednLats = nmlat
      if (allocated(ie%needLats)) deallocate(ie%needLats)
      if (allocated(ie%needMlts)) deallocate(ie%needMlts)
      allocate(ie%needLats(nmlon, nmlat))
      allocate(ie%needMlts(nmlon, nmlat))
    endif

    do iLat = 1, nmlat
      do iMlt = 1, nmlon
        ie%needLats(iMlt, iLat) = ylatm(iLat)*(180.0/pi)
        ie%needMlts(iMlt, iLat) = ((ylonm(iMlt) - sunlons(1))*12.0/pi) + 12.0
      enddo
    enddo

    ie%needHpN = power
    ie%needHpS = power

    if (ie%iEfield_ > 0) then
      allocate(potential(nmlon, nmlat))

      call ie%get_potential(potential)

      do iLat = 1, nmlat
        do iMlt = 1, nmlon
          phihm(iMlt, iLat) = potential(iMlt, iLat)
        enddo
        ! Periodic point
        phihm(nmlonp1, iLat) = phihm(1, iLat)
      enddo

      deallocate(potential)
      call ie%get_electron_diffuse_aurora(ie_eflux_mag, ie_avee_mag)
    else
      ! NONE potential
      do iLat = 1, nmlat0
        do iMlt = 1, nmlonp1
          phihm(iMlt, iLat) = 0.0
        enddo
      enddo
    endif

  end subroutine update_ie_potential
#endif
end module ModIETIEGCM
