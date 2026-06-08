module ModIETIEGCM
#ifdef HAVEMILE
  use ModIE, only: ieModel, iHeelis_, iWeimer05_
  implicit none
  
  type(ieModel), save :: ie

contains

  subroutine init_ie()
    implicit none
    ! Basic initialization if needed
    ie%iDebugLevel = 1
  end subroutine init_ie

  subroutine update_ie_potential()
    use params_module, only: nmlon, nmlonp1, nmlat
    use cons_module, only: ylonm, ylatm, pi
    use input_module, only: potential_model
    use magfield_module, only: sunlons
    use pdynamo_module, only: phihm, nmlat0
    use ModTiegcmHeelis, only: offc_ie=>offc, dskofc_ie=>dskofc, &
                               phin_ie=>phin, phid_ie=>phid, theta0_ie=>theta0, &
                               psie_ie=>psie, psim_ie=>psim, pcen_ie=>pcen, &
                               phidm0_ie=>phidm0, phidp0_ie=>phidp0, &
                               phinm0_ie=>phinm0, phinp0_ie=>phinp0, rr1_ie=>rr1
    use aurora_module, only: offc, dskofc, phin, phid, theta0, &
                             psie, psim, pcen, phidm0, phidp0, &
                             phinm0, phinp0, rr1
    use ModIE, only: iHeelis_, iWeimer05_
    implicit none

    integer :: iMlt, iLat
    real, allocatable :: potential(:,:)

    integer, external :: efield_interpret_name

    ! Map TIEGCM string to IE model ID using Electrodynamics native interpreter
    ie%iEfield_ = efield_interpret_name(potential_model)

    if (ie%iEfield_ == iHeelis_) then
      ! Copy parameters from aurora_module
      offc_ie = offc
      dskofc_ie = dskofc
      phin_ie = phin
      phid_ie = phid
      theta0_ie = theta0
      psie_ie = psie
      psim_ie = psim
      pcen_ie = pcen
      phidm0_ie = phidm0
      phidp0_ie = phidp0
      phinm0_ie = phinm0
      phinp0_ie = phinp0
      rr1_ie = rr1
    endif

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
        ie%needLats(iMlt, iLat) = ylatm(iLat) * (180.0 / pi)
        ie%needMlts(iMlt, iLat) = ((ylonm(iMlt) - sunlons(1)) * 12.0 / pi) + 12.0
      enddo
    enddo

    if (ie%iEfield_ > 0) then
      allocate(potential(nmlon, nmlat))
      call ie%get_potential(potential)
      
      ! Map back to TIEGCM phihm (kV -> V is handled inside, potential is V)
      do iLat = 1, nmlat
        do iMlt = 1, nmlon
          phihm(iMlt, iLat) = potential(iMlt, iLat)
        enddo
        ! Periodic point
        phihm(nmlonp1, iLat) = phihm(1, iLat)
      enddo
      deallocate(potential)
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
