using Content.Server.Power.EntitySystems;
using Content.Server._EinsteinEngines.Silicon.Charge;
using Content.Server.Power.Components;
using Content.Shared._EinsteinEngines.Silicon.Components;
using Content.Shared.EntityEffects.Effects;
using Robust.Shared.Utility;

namespace Content.Server._EinsteinEngines.Silicon.Charge;

public sealed class RechargeSiliconBatterySystem : EntitySystem
{
    [Dependency] private readonly BatterySystem _battery = default!;
    [Dependency] private readonly SiliconChargeSystem _siliconCharge = default!;

    public override void Initialize()
    {
        SubscribeLocalEvent<RechargeSiliconBatteryEvent>(OnRecharge);
    }

    private void OnRecharge(RechargeSiliconBatteryEvent ev)
    {
        if (!_siliconCharge.TryGetSiliconBattery(ev.Uid, out var battery))
            return;

        var amount = battery.MaxCharge * ev.Percent;
        _battery.SetCharge(ev.Uid, battery.CurrentCharge + amount, battery);
    }
}