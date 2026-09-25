using Robust.Shared.Prototypes;

namespace Content.Shared.EntityEffects.Effects;

public sealed partial class RechargeSiliconBattery : EntityEffect
{
    [DataField("percent")]
    public float Percent = 0.25f;

    public override void Effect(EntityEffectBaseArgs args)
    {
        args.EntityManager.EventBus.RaiseLocalEvent(
            args.TargetEntity,
            new RechargeSiliconBatteryEvent(args.TargetEntity, Percent));
    }

    protected override string? ReagentEffectGuidebookText(IPrototypeManager prototype, IEntitySystemManager entSys)
        => null;
}

public readonly record struct RechargeSiliconBatteryEvent(EntityUid Uid, float Percent);
