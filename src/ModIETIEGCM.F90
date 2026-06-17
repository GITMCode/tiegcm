module ModIETIEGCM
#ifdef HAVEMILE
  use ModIE
  use ModIndices, only: init_imf, init_ae, init_hpi, get_index, get_nValues, set_time
  use params_module, only: nmlon, nmlonp1, nmlat, spval
  implicit none

  type(ieModel), save :: ie

contains

  subroutine init_ie()
    use input_module, only: potential_model, aurora_model, &
                             srcindices_imf_file, srcindices_ae_file, &
                             srcindices_hpi_file
    implicit none

    ie = iemodel()
    call ie%efield_model(potential_model)
    if (aurora_model /= 'emery') then
      call ie%aurora_model(aurora_model)
    else
      call ie%aurora_model('zero')
    endif
    call ie%model_dir("../ext/Electrodynamics/data/ext/")
    call ie%init()

    if (aurora_model /= 'emery' .and. ie%iAurora_ == -1) then
      write(6,"(/,'>>> MILE: unrecognized aurora_model: ',a)") trim(aurora_model)
      write(6,"('Valid options (with HAVEMILE): fre, fta, hpi, pem, zero, amie')")
      call shutdown('aurora_model')
    endif

    if (len_trim(srcindices_imf_file) > 0) &
      call init_imf(trim(srcindices_imf_file))
    if (len_trim(srcindices_ae_file) > 0) then
      call init_ae(trim(srcindices_ae_file))
      if (len_trim(srcindices_hpi_file) > 0) then
        call init_hpi(trim(srcindices_hpi_file))
      else
        call init_hpi()  ! AE->HPI conversion
      endif
    elseif (len_trim(srcindices_hpi_file) > 0) then
      call init_hpi(trim(srcindices_hpi_file))
    endif

  end subroutine init_ie

  ! Set all indices on ie before each timestep. Owns time-setting for
  ! both Electrodynamics (ie%time_ymdhms) and srcIndices (set_time).
  ! Falls back to namelist values when no index file is loaded.
  subroutine set_ie_indices(byimf_in, bzimf_in, swvel_in, swden_in)
    use input_module, only: power, kp, byimf, bzimf, swvel, swden
    use init_module, only: iyear, iday, uthr
    use wei05sc, only: cvt2md
    implicit none
    real, intent(in), optional :: byimf_in, bzimf_in, swvel_in, swden_in
    integer :: imo, ida, ihour, imin, isec
    real :: val

    call cvt2md(6, iyear, iday, imo, ida)
    ihour = int(uthr)
    imin  = int((uthr - real(ihour)) * 60.0)
    isec  = 0

    ! Time must be set before check_indices fires inside get_potential
    call ie%time_ymdhms(iyear, imo, ida, ihour, imin, isec)
    call set_time(iyear, imo, ida, ihour, imin, isec)

    if (get_nValues('imfby') > 0) then
      call get_index('imfby', val); ie%needImfBy = val
    elseif (present(byimf_in)) then
      ie%needImfBy = byimf_in
    else
      ie%needImfBy = byimf
    endif

    if (get_nValues('imfbz') > 0) then
      call get_index('imfbz', val); ie%needImfBz = val
    elseif (present(bzimf_in)) then
      ie%needImfBz = bzimf_in
    else
      ie%needImfBz = bzimf
    endif

    if (get_nValues('swvmag') > 0) then
      call get_index('swvmag', val); ie%needSwV = val
    elseif (present(swvel_in)) then
      ie%needSwV = swvel_in
    else
      ie%needSwV = swvel
    endif

    if (get_nValues('swn') > 0) then
      call get_index('swn', val); ie%needSwN = val
    elseif (present(swden_in)) then
      ie%needSwN = swden_in
    else
      ie%needSwN = swden
    endif

    if (get_nValues('hpin') > 0) then
      call get_index('hpin', val); ie%needHpN = val
      call get_index('hpis', val); ie%needHpS = val
    else
      ie%needHpN = power
      ie%needHpS = power
    endif

    if (get_nValues('au') > 0) then
      call get_index('au', val); ie%needAu = val
      call get_index('al', val); ie%needAl = val
    endif

    if (kp /= spval) ie%needKp = kp

  end subroutine set_ie_indices

  subroutine update_ie_potential(byimf_in, bzimf_in, swvel_in, swden_in)
    use cons_module, only: ylonm, ylatm, pi
    use magfield_module, only: sunlons
    use pdynamo_module, only: phihm, nmlat0
    use aurora_module, only: ie_eflux_mag, ie_avee_mag

    implicit none

    integer :: iMlt, iLat
    real, allocatable :: potential(:, :)
    real, intent(in), optional :: byimf_in, bzimf_in, swvel_in, swden_in

    call set_ie_indices(byimf_in, bzimf_in, swvel_in, swden_in)

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
