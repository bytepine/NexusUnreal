// Copyright Epic Games, Inc. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"

/** UE4 桩：对齐 Enhanced Input 的 FInputActionValue。 */
struct FInputActionValue
{
	template <typename T>
	T Get() const
	{
		return T();
	}
};
